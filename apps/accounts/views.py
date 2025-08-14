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
from django.db import transaction
from django.core.paginator import Paginator
from typing import cast
import json
import logging

from .models import User, UserProfile, UserSession, UserAlert, UserNotification
from .forms import (
    CustomLoginForm, CustomRegistrationForm, UserProfileForm,
    UserPreferencesForm, PasswordChangeForm, OnboardingForm
)

logger = logging.getLogger(__name__)


class CustomLoginView(LoginView):
    """Enhanced login view with session tracking"""
    
    form_class = CustomLoginForm
    template_name = 'accounts/login.html'
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
            return reverse('accounts:onboarding')
        
        # Redirect to next parameter or dashboard
        return self.get_redirect_url() or reverse('dashboard:home')


class RegistrationView(CreateView):
    """User registration view"""
    
    model = User
    form_class = CustomRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:onboarding')
    
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
    return redirect('accounts:login')


@login_required
def dashboard_view(request):
    """User dashboard view"""
    user = request.user
    
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
    
    context = {
        'user': user,
        'recent_alerts': recent_alerts,
        'recent_sessions': recent_sessions,
        'profile_completion': profile_completion,
        'unread_alerts_count': recent_alerts.count(),
    }
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_view(request):
    """User profile view"""
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            
            # Update profile completion status
            user.profile_completed = True
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': calculate_profile_completion(user),
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def preferences_view(request):
    """User preferences view"""
    user = request.user
    
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully!')
            return redirect('accounts:preferences')
    else:
        form = UserPreferencesForm(instance=user)
    
    return render(request, 'accounts/preferences.html', {'form': form})


@login_required
def change_password_view(request):
    """Change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)  # Keep user logged in
            messages.success(request, 'Password changed successfully!')
            logger.info(f"User {request.user.username} changed password")
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


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
    
    return render(request, 'accounts/onboarding.html', {'form': form})


@login_required
def alerts_view(request):
    """User alerts management view"""
    user = request.user
    
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
    
    return render(request, 'accounts/alerts.html', context)


@login_required
@require_http_methods(["POST"])
def mark_alert_read(request, alert_id):
    """Mark alert as read"""
    alert = get_object_or_404(UserNotification, id=alert_id, user=request.user)
    alert.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('accounts:alerts')


@login_required
@require_http_methods(["POST"])
def mark_all_alerts_read(request):
    """Mark all alerts as read"""
    UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'All alerts marked as read.')
    return redirect('accounts:alerts')


@login_required
def sessions_view(request):
    """User sessions management view"""
    user = request.user
    
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
    
    return render(request, 'accounts/sessions.html', context)


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
    return redirect('accounts:sessions')


@login_required
def account_security_view(request):
    """Account security overview"""
    user = request.user
    
    # Get recent login activity
    recent_logins = UserSession.objects.filter(
        user=user
    ).order_by('-login_time')[:10]
    
    # Security metrics
    active_sessions = UserSession.objects.filter(user=user, is_active=True).count()
    total_logins = UserSession.objects.filter(user=user).count()
    
    context = {
        'recent_logins': recent_logins,
        'active_sessions': active_sessions,
        'total_logins': total_logins,
        'current_ip': get_client_ip(request),
    }
    
    return render(request, 'accounts/security.html', context)


# AJAX Views
@login_required
def get_unread_alerts_count(request):
    """Get count of unread alerts (AJAX)"""
    count = UserNotification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def check_username_availability(request):
    """Check username availability (AJAX)"""
    username = request.GET.get('username', '')
    is_available = not User.objects.filter(username=username).exists()
    return JsonResponse({'available': is_available})


@login_required
def check_email_availability(request):
    """Check email availability (AJAX)"""
    email = request.GET.get('email', '')
    is_available = not User.objects.filter(email=email).exists()
    return JsonResponse({'available': is_available})


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
    if user.preferred_stocks.exists():
        completed_fields += 1
    if user.preferred_industries.exists():
        completed_fields += 1
    
    # Check profile fields
    if hasattr(user, 'profile'):
        profile = user.profile
        if profile.experience_years is not None:
            completed_fields += 1
        if profile.investment_focus:
            completed_fields += 1
        if profile.risk_tolerance:
            completed_fields += 1
        if profile.portfolio_size_range:
            completed_fields += 1
    
    return round((completed_fields / total_fields) * 100)
