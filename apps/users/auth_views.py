"""
Authentication views for GPW2 Trading Intelligence Platform
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView, FormView
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction, models
from django.core.paginator import Paginator
from typing import cast
import json
import logging

from .models import User, UserProfile, UserSession, UserNotification
from .forms import (
    CustomLoginForm, 
    CustomUserCreationForm as CustomRegistrationForm,
    TradingPreferencesForm as UserPreferencesForm,
    UserProfileForm,
    OnboardingForm,
)

logger = logging.getLogger(__name__)


class CustomLoginView(LoginView):
    """Enhanced login view with session tracking"""
    
    form_class = CustomLoginForm
    template_name = 'users/login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Login user and track session"""
        response = super().form_valid(form)
        
        # Handle remember me
        if form.cleaned_data.get('remember_me'):
            self.request.session.set_expiry(86400 * 30)  # 30 days
        else:
            self.request.session.set_expiry(0)  # Browser session
        
        # Track login
        user = form.get_user()
        UserSession.objects.create(
            user=user,
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            is_active=True
        )
        
        messages.success(self.request, f'Welcome back, {user.get_full_name() or user.username}!')
        logger.info(f"User {user.username} logged in from {self.get_client_ip()}")
        
        return response
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def get_success_url(self):
        """Redirect to dashboard or onboarding"""
        user = cast(User, self.request.user)
        
        # Check if user needs onboarding
        if hasattr(user, 'onboarding_completed') and not user.onboarding_completed:
            return reverse('users:onboarding')
        
        # Redirect to next parameter or dashboard
        return self.get_redirect_url() or reverse('dashboard:home')


class RegistrationView(CreateView):
    """User registration view"""
    
    model = User
    form_class = CustomRegistrationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:onboarding')
    
    def dispatch(self, request, *args, **kwargs):
        """Redirect authenticated users"""
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Register user and auto-login"""
        response = super().form_valid(form)
        
        # Auto-login the user
        user = form.save()
        login(self.request, user)
        
        # Track registration
        UserSession.objects.create(
            user=user,
            ip_address=self.get_client_ip(),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            is_active=True
        )
        
        messages.success(
            self.request,
            f'Welcome to GPW2 Trading Intelligence, {user.get_full_name()}! Let\'s get you set up.'
        )
        logger.info(f"New user registered: {user.username}")
        
        return response
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


@require_http_methods(["POST"])
def logout_view(request):
    """Logout view with session cleanup"""
    if request.user.is_authenticated:
        # Mark current session as inactive
        UserSession.objects.filter(
            user=request.user,
            is_active=True,
            ip_address=get_client_ip(request)
        ).update(is_active=False)
        
        logger.info(f"User {request.user.username} logged out")
        
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('users:login')


@login_required
def dashboard_view(request):
    """Enhanced user dashboard view with trading data"""
    user = cast(User, request.user)
    
    # Get user's recent alerts
    recent_alerts = UserNotification.objects.filter(
        user=user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Get user's recent sessions
    recent_sessions = UserSession.objects.filter(
        user=user
    ).order_by('-login_time')[:5]
    
    # Check if profile is incomplete
    profile_completion = calculate_profile_completion(user)
    
    # Get trading data
    from apps.core.models import StockSymbol, ScrapingExecution
    from apps.scrapers.models import StockData
    from django.utils import timezone
    from datetime import timedelta
    
    # Get monitored stocks with latest prices
    monitored_stocks = StockSymbol.objects.filter(
        is_monitored=True, 
        is_active=True
    )[:6]
    
    # Get recent stock data for chart
    stock_data = []
    if monitored_stocks:
        for stock in monitored_stocks:
            try:
                latest_data = StockData.objects.filter(
                    stock=stock  # Changed from symbol to stock
                ).select_related('stock').order_by('-created_at').first()
                
                if latest_data:
                    stock_data.append({
                        'company__symbol': stock.symbol,  # Changed to match template
                        'company__name': stock.name,     # Changed to match template
                        'price': latest_data.close_price,
                        'change': latest_data.price_change,
                        'change_percent': latest_data.price_change_percent,
                        'volume': latest_data.volume,
                        'timestamp': latest_data.data_timestamp or latest_data.created_at
                    })
            except Exception as e:
                print(f"Error getting data for {stock.symbol}: {e}")  # Debug info
                pass  # Skip if StockData model doesn't exist yet
    
    # Get recent scraper executions
    recent_executions = ScrapingExecution.objects.filter(
        started_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-started_at')[:5]
    
    # Get system stats
    total_stocks = StockSymbol.objects.filter(is_active=True).count()
    active_schedules = 0
    scheduler_status = False
    success_rate = 0.0
    last_execution = None
    last_update = timezone.now()
    
    try:
        from apps.core.models import ScrapingSchedule
        active_schedules = ScrapingSchedule.objects.filter(is_active=True).count()
        
        # Check if scheduler is running by checking recent executions
        recent_exec = recent_executions.first()
        if recent_exec and recent_exec.started_at >= timezone.now() - timedelta(hours=1):
            scheduler_status = True
            last_execution = recent_exec.started_at
        
        # Calculate success rate
        if recent_executions.exists():
            successful = recent_executions.filter(success=True).count()
            success_rate = (successful / recent_executions.count()) * 100
            
        # Get latest stock data timestamp
        if stock_data:
            latest_stock = max(stock_data, key=lambda x: x.get('timestamp', timezone.now()))
            last_update = latest_stock.get('timestamp', timezone.now())
            
    except Exception as e:
        print(f"Error getting system stats: {e}")
        pass
    
    context = {
        'user': user,
        'recent_alerts': recent_alerts,
        'recent_sessions': recent_sessions,
        'profile_completion': profile_completion,
        'unread_alerts_count': recent_alerts.count(),
        'monitored_stocks': monitored_stocks,
        'stock_data': stock_data,
        'recent_executions': recent_executions,
        'recent_executions_count': recent_executions.count(),
        'total_stocks': total_stocks,
        'total_companies': total_stocks,  # Template expects total_companies
        'active_stocks': monitored_stocks.count(),  # Template expects active_stocks
        'active_schedules': active_schedules,
        'scheduler_status': scheduler_status,
        'success_rate': success_rate,
        'last_execution': last_execution,
        'last_update': last_update,
    }
    
    return render(request, 'users/dashboard.html', context)


@login_required
def watchlist_view(request):
    """User watchlist view - shows monitored stocks with detailed information"""
    user = cast(User, request.user)
    
    from apps.core.models import StockSymbol
    from apps.scrapers.models import StockData
    from django.utils import timezone
    from datetime import timedelta, date
    
    # Get all monitored stocks
    monitored_stocks = StockSymbol.objects.filter(
        is_monitored=True, 
        is_active=True
    ).select_related().order_by('symbol')
    
    # Prepare stock data with latest prices
    watchlist_data = []
    
    for stock in monitored_stocks:
        try:
            # Get latest stock data
            latest_data = StockData.objects.filter(
                stock=stock
            ).select_related('stock', 'trading_session').order_by('-created_at').first()
            
            # Get previous day data for comparison (look for most recent trading session before current)
            if latest_data and latest_data.trading_session:
                previous_data = StockData.objects.filter(
                    stock=stock,
                    trading_session__date__lt=latest_data.trading_session.date
                ).order_by('-trading_session__date').first()
            else:
                previous_data = None
            
            # Calculate daily change if we have both current and previous data
            daily_change = None
            daily_change_percent = None
            
            if latest_data and previous_data and latest_data.close_price and previous_data.close_price:
                daily_change = latest_data.close_price - previous_data.close_price
                daily_change_percent = (daily_change / previous_data.close_price) * 100
            # Note: We don't use latest_data.price_change as fallback because that's intraday change, not daily change
            
            # Get recent volume average (for comparison)
            week_ago = date.today() - timedelta(days=7)
            recent_volume_avg = StockData.objects.filter(
                stock=stock,
                trading_session__date__gte=week_ago,
                volume__isnull=False
            ).aggregate(avg_volume=models.Avg('volume'))['avg_volume']
            
            # Volume change indicator
            volume_change_indicator = None
            if latest_data and latest_data.volume and recent_volume_avg:
                if latest_data.volume > recent_volume_avg * 1.5:
                    volume_change_indicator = 'high'
                elif latest_data.volume < recent_volume_avg * 0.5:
                    volume_change_indicator = 'low'
                else:
                    volume_change_indicator = 'normal'
            
            watchlist_item = {
                'stock': stock,
                'latest_data': latest_data,
                'current_price': latest_data.close_price if latest_data else None,
                'daily_change': daily_change,
                'daily_change_percent': daily_change_percent,
                'volume': latest_data.volume if latest_data else None,
                'volume_change': volume_change_indicator,
                'last_update': latest_data.data_timestamp if latest_data else None,
                'trading_session': latest_data.trading_session if latest_data else None,
            }
            
            watchlist_data.append(watchlist_item)
            
        except Exception as e:
            logger.error(f"Error getting data for {stock.symbol}: {e}")
            # Add stock with minimal data even if there's an error
            watchlist_item = {
                'stock': stock,
                'latest_data': None,
                'current_price': None,
                'daily_change': None,
                'daily_change_percent': None,
                'volume': None,
                'volume_change': None,
                'last_update': None,
                'trading_session': None,
            }
            watchlist_data.append(watchlist_item)
    
    # Get overall market summary
    market_summary = {
        'total_monitored': monitored_stocks.count(),
        'active_today': sum(1 for item in watchlist_data if item['latest_data']),
        'gainers': sum(1 for item in watchlist_data if item['daily_change'] and item['daily_change'] > 0),
        'losers': sum(1 for item in watchlist_data if item['daily_change'] and item['daily_change'] < 0),
    }
    
    context = {
        'user': user,
        'watchlist_data': watchlist_data,
        'market_summary': market_summary,
        'current_time': timezone.now(),
    }
    
    return render(request, 'users/watchlist.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_stock_monitoring_ajax(request, symbol):
    """Toggle stock monitoring status via AJAX from watchlist"""
    from apps.core.models import StockSymbol
    import json
    
    try:
        stock = get_object_or_404(StockSymbol, symbol=symbol.upper())
        stock.is_monitored = not stock.is_monitored
        stock.save()
        
        action = "dodana do" if stock.is_monitored else "usunięta z"
        
        return JsonResponse({
            'success': True,
            'is_monitored': stock.is_monitored,
            'message': f'Spółka {stock.symbol} została {action} obserwowanych',
            'symbol': stock.symbol,
            'name': stock.name
        })
        
    except StockSymbol.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Nie znaleziono spółki {symbol}'
        }, status=404)
        
    except Exception as e:
        logger.error(f"Error toggling monitoring for {symbol}: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Wystąpił błąd podczas zmiany statusu monitorowania'
        }, status=500)


@login_required
def watchlist_data_api(request):
    """API endpoint to get watchlist data in JSON format for auto-refresh"""
    user = cast(User, request.user)
    
    from apps.core.models import StockSymbol
    from apps.scrapers.models import StockData
    from django.utils import timezone
    from datetime import timedelta, date
    import json
    from decimal import Decimal
    
    try:
        # Get all monitored stocks
        monitored_stocks = StockSymbol.objects.filter(
            is_monitored=True, 
            is_active=True
        ).select_related().order_by('symbol')
        
        # Prepare stock data with latest prices
        watchlist_data = []
        
        for stock in monitored_stocks:
            try:
                # Get latest stock data
                latest_data = StockData.objects.filter(
                    stock=stock
                ).select_related('stock', 'trading_session').order_by('-created_at').first()
                
                # Get previous trading session data for comparison (look for most recent trading session before current)
                if latest_data and latest_data.trading_session:
                    previous_data = StockData.objects.filter(
                        stock=stock,
                        trading_session__date__lt=latest_data.trading_session.date
                    ).order_by('-trading_session__date').first()
                else:
                    previous_data = None
                
                # Calculate daily change if we have both current and previous data
                daily_change = None
                daily_change_percent = None
                
                if latest_data and previous_data and latest_data.close_price and previous_data.close_price:
                    daily_change = float(latest_data.close_price - previous_data.close_price)
                    daily_change_percent = float((latest_data.close_price - previous_data.close_price) / previous_data.close_price * 100)
                # Note: We don't use latest_data.price_change as fallback because that's intraday change, not daily change
                
                # Get recent volume average (for comparison)
                week_ago = date.today() - timedelta(days=7)
                recent_volume_avg = StockData.objects.filter(
                    stock=stock,
                    trading_session__date__gte=week_ago,
                    volume__isnull=False
                ).aggregate(avg_volume=models.Avg('volume'))['avg_volume']
                
                # Volume change indicator
                volume_change_indicator = None
                if latest_data and latest_data.volume and recent_volume_avg:
                    if latest_data.volume > recent_volume_avg * 1.5:
                        volume_change_indicator = 'high'
                    elif latest_data.volume < recent_volume_avg * 0.5:
                        volume_change_indicator = 'low'
                    else:
                        volume_change_indicator = 'normal'
                
                watchlist_item = {
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': stock.sector,
                    'current_price': float(latest_data.close_price) if latest_data and latest_data.close_price else None,
                    'daily_change': daily_change,
                    'daily_change_percent': daily_change_percent,
                    'volume': int(latest_data.volume) if latest_data and latest_data.volume else None,
                    'volume_change': volume_change_indicator,
                    'last_update': latest_data.data_timestamp.isoformat() if latest_data and latest_data.data_timestamp else None,
                    'last_update_formatted': latest_data.data_timestamp.strftime('%H:%M:%S') if latest_data and latest_data.data_timestamp else None,
                    'last_update_date_formatted': latest_data.data_timestamp.strftime('%d.%m.%Y') if latest_data and latest_data.data_timestamp else None,
                }
                
                watchlist_data.append(watchlist_item)
                
            except Exception as e:
                logger.error(f"Error getting data for {stock.symbol}: {e}")
                # Add stock with minimal data even if there's an error
                watchlist_item = {
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': stock.sector,
                    'current_price': None,
                    'daily_change': None,
                    'daily_change_percent': None,
                    'volume': None,
                    'volume_change': None,
                    'last_update': None,
                    'last_update_formatted': 'Brak danych',
                    'last_update_date_formatted': '',
                }
                watchlist_data.append(watchlist_item)
        
        # Get overall market summary
        market_summary = {
            'total_monitored': monitored_stocks.count(),
            'active_today': sum(1 for item in watchlist_data if item['last_update']),
            'gainers': sum(1 for item in watchlist_data if item['daily_change'] and item['daily_change'] > 0),
            'losers': sum(1 for item in watchlist_data if item['daily_change'] and item['daily_change'] < 0),
        }
        
        return JsonResponse({
            'success': True,
            'watchlist_data': watchlist_data,
            'market_summary': market_summary,
            'current_time': timezone.now().isoformat(),
            'current_time_formatted': timezone.now().strftime('%d.%m.%Y %H:%M:%S'),
        })
        
    except Exception as e:
        logger.error(f"Error fetching watchlist data: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Wystąpił błąd podczas pobierania danych'
        }, status=500)


@login_required
def profile_view(request):
    """User profile view"""
    user = cast(User, request.user)
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            
            # Update profile completion status
            user.profile_completed = True
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            return redirect('users:profile')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': calculate_profile_completion(user),
    }
    
    return render(request, 'users/profile.html', context)


@login_required
def preferences_view(request):
    """User preferences view"""
    user = cast(User, request.user)
    
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully!')
            return redirect('users:preferences')
    else:
        form = UserPreferencesForm(instance=user)
    
    return render(request, 'users/preferences.html', {'form': form})


@login_required
def onboarding_view(request):
    """Onboarding flow for new users"""
    user = cast(User, request.user)
    
    # Redirect if already completed
    if hasattr(user, 'onboarding_completed') and user.onboarding_completed:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = OnboardingForm(request.POST)
        if form.is_valid():
            form.save(user)
            messages.success(request, 'Welcome! Your account is now set up.')
            logger.info(f"User {user.username} completed onboarding")
            return redirect('dashboard:home')
    else:
        form = OnboardingForm()
    
    return render(request, 'users/onboarding.html', {'form': form})


@login_required
def alerts_view(request):
    """User alerts management view"""
    user = cast(User, request.user)
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    alert_type = request.GET.get('type', 'all')
    
    # Build query
    alerts = UserNotification.objects.filter(user=user)
    
    if status_filter == 'unread':
        alerts = alerts.filter(is_read=False)
    elif status_filter == 'read':
        alerts = alerts.filter(is_read=True)
    
    if alert_type != 'all':
        alerts = alerts.filter(notification_type=alert_type)
    
    alerts = alerts.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(alerts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get notification type choices for filter
    alert_types = UserNotification._meta.get_field('notification_type').choices
    
    context = {
        'page_obj': page_obj,
        'alerts': page_obj.object_list,
        'status_filter': status_filter,
        'alert_type': alert_type,
        'alert_types': alert_types,
        'unread_count': UserNotification.objects.filter(user=user, is_read=False).count(),
    }
    
    return render(request, 'users/alerts.html', context)


@login_required
@require_http_methods(["POST"])
def mark_alert_read(request, alert_id):
    """Mark alert as read"""
    alert = get_object_or_404(UserNotification, id=alert_id, user=request.user)
    alert.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('users:alerts')


@login_required
@require_http_methods(["POST"])
def mark_all_alerts_read(request):
    """Mark all alerts as read"""
    UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'All alerts marked as read.')
    return redirect('users:alerts')


@login_required
def sessions_view(request):
    """User sessions management view"""
    user = cast(User, request.user)
    
    sessions = UserSession.objects.filter(user=user).order_by('-login_time')
    
    # Pagination
    paginator = Paginator(sessions, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'sessions': page_obj.object_list,
        'current_ip': get_client_ip(request),
    }
    
    return render(request, 'users/sessions.html', context)


@login_required
@require_http_methods(["POST"])
def terminate_session(request, session_id):
    """Terminate a user session"""
    session = get_object_or_404(UserSession, id=session_id, user=request.user)
    session.is_active = False
    session.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'Session terminated successfully.')
    return redirect('users:sessions')


# AJAX Views
@login_required
def get_unread_alerts_count(request):
    """Get count of unread alerts (AJAX)"""
    count = UserNotification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})


# Utility Functions
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def calculate_profile_completion(user):
    """Calculate profile completion percentage"""
    total_fields = 10
    completed_fields = 0
    
    # Check user fields
    if user.full_name:
        completed_fields += 1
    if user.email:
        completed_fields += 1
    if user.phone_number:
        completed_fields += 1
    if user.company:
        completed_fields += 1
    
    # Check profile fields
    try:
        profile = user.profile
        if profile.experience_years is not None:
            completed_fields += 1
        if profile.investment_focus:
            completed_fields += 1
        if profile.risk_tolerance:
            completed_fields += 1
        if profile.portfolio_size_range:
            completed_fields += 1
        if profile.license_number:
            completed_fields += 1
        completed_fields += 1  # Profile exists
    except UserProfile.DoesNotExist:
        pass
    
    return round((completed_fields / total_fields) * 100)
