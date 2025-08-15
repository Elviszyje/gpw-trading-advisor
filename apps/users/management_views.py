"""
Management interface views for business operations - Simplified version
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from datetime import date, timedelta, datetime
import json
import logging

from apps.core.models import StockSymbol, ScrapingSchedule, ScrapingExecution, TradingSession, Market, Industry
from apps.scrapers.models import ScrapingSource, ScrapingJob

# Try to import optional models that may not exist
try:
    from apps.scrapers.models import StockData
except ImportError:
    StockData = None

try:
    from apps.scrapers.models import CompanyCalendarEvent
except ImportError:
    CompanyCalendarEvent = None

logger = logging.getLogger(__name__)


@login_required
@staff_member_required
def companies_list(request):
    """Lista spółek z możliwością filtrowania"""
    search_query = request.GET.get('search', '')
    market_filter = request.GET.get('market', '')
    monitored_filter = request.GET.get('monitored', '')
    status_filter = request.GET.get('status', 'active')  # Default to active only
    
    # Base queryset - default to active companies only
    if status_filter == 'all':
        companies = StockSymbol.objects.all()
    elif status_filter == 'inactive':
        companies = StockSymbol.objects.filter(is_active=False)
    else:  # 'active' or empty
        companies = StockSymbol.objects.filter(is_active=True)
    
    # Apply filters
    if search_query:
        companies = companies.filter(
            Q(symbol__icontains=search_query) | 
            Q(name__icontains=search_query)
        )
    
    if market_filter:
        companies = companies.filter(market=market_filter)
    
    if monitored_filter:
        if monitored_filter == 'true':
            companies = companies.filter(is_monitored=True)
        elif monitored_filter == 'false':
            companies = companies.filter(is_monitored=False)
    
    # Statistics
    total_companies = companies.count()
    monitored_companies = companies.filter(is_monitored=True).count()
    markets = StockSymbol.objects.values_list('market', flat=True).distinct()
    
    # Additional stats for status filter
    all_companies_count = StockSymbol.objects.count()
    active_companies_count = StockSymbol.objects.filter(is_active=True).count()
    inactive_companies_count = StockSymbol.objects.filter(is_active=False).count()
    
    stats = {
        'total': total_companies,
        'monitored': monitored_companies,
        'markets': len([m for m in markets if m]),
        'all_companies': all_companies_count,
        'active_companies': active_companies_count,
        'inactive_companies': inactive_companies_count,
    }
    
    # Pagination
    paginator = Paginator(companies, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'markets': [m for m in markets if m],
        'search_query': search_query,
        'market_filter': market_filter,
        'monitored_filter': monitored_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'management/companies_list.html', context)


@login_required
def company_detail(request, symbol):
    """Szczegóły spółki"""
    company = get_object_or_404(StockSymbol, symbol=symbol)
    
    # Get latest stock data if available - group by trading session to show one record per day
    latest_data = []
    if StockData:
        # Get unique trading sessions and then the latest record for each day
        from django.db.models import Max
        
        # Get latest data_timestamp for each trading session
        latest_by_session = StockData.objects.filter(
            stock=company
        ).values('trading_session').annotate(
            latest_timestamp=Max('data_timestamp')
        )
        
        # Get the actual records with those timestamps
        latest_data = []
        for session_data in latest_by_session:
            record = StockData.objects.filter(
                stock=company,
                trading_session_id=session_data['trading_session'],
                data_timestamp=session_data['latest_timestamp']
            ).select_related('trading_session').first()
            
            if record:
                latest_data.append(record)
        
        # Sort by trading session date descending and limit to 20
        latest_data = sorted(latest_data, key=lambda x: x.trading_session.date, reverse=True)[:20]
    
    # Get calendar events if available
    calendar_events = []
    if CompanyCalendarEvent:
        calendar_events = CompanyCalendarEvent.objects.filter(
            stock_symbol=company
        ).order_by('-event_date')[:10]
    
    # Basic stats 
    stats = {
        'data_points': len(latest_data),
        'calendar_events': len(calendar_events),
        'last_update': company.updated_at if hasattr(company, 'updated_at') else None,
    }
    
    context = {
        'company': company,
        'latest_data': latest_data,
        'calendar_events': calendar_events,
        'stats': stats,
        'today': timezone.now().date(),
    }
    
    return render(request, 'management/company_detail.html', context)


@login_required
@staff_member_required
def company_edit(request, symbol):
    """Edycja spółki"""
    company = get_object_or_404(StockSymbol, symbol=symbol)
    
    if request.method == 'POST':
        # Process form data
        company.name = request.POST.get('name', company.name).strip()
        company.sector = request.POST.get('sector', company.sector).strip()
        company.business_description = request.POST.get('business_description', company.business_description).strip()
        company.website = request.POST.get('website', company.website).strip()
        company.isin_code = request.POST.get('isin_code', company.isin_code).strip()
        company.is_monitored = request.POST.get('is_monitored') == 'on'
        
        # Handle market selection
        market_id = request.POST.get('market')
        if market_id:
            try:
                market = Market.objects.get(id=market_id)
                company.market = market
            except Market.DoesNotExist:
                pass
        else:
            company.market = None
        
        # Handle primary industry selection
        industry_id = request.POST.get('primary_industry')
        if industry_id:
            try:
                industry = Industry.objects.get(id=industry_id)
                company.primary_industry = industry
            except Industry.DoesNotExist:
                pass
        else:
            company.primary_industry = None
        
        # Handle market cap
        market_cap_str = request.POST.get('market_cap', '').strip()
        if market_cap_str:
            try:
                company.market_cap = int(market_cap_str.replace(' ', '').replace(',', ''))
            except ValueError:
                company.market_cap = None
        else:
            company.market_cap = None
        
        # Handle keywords (JSON field)
        keywords_str = request.POST.get('keywords', '').strip()
        if keywords_str:
            try:
                # Split by commas and clean up
                keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                company.keywords = keywords
            except:
                pass
        else:
            company.keywords = []
        
        try:
            company.save()
            messages.success(request, f'Spółka {company.symbol} została zaktualizowana pomyślnie.')
            return redirect('users:company_detail', symbol=symbol)
        except Exception as e:
            messages.error(request, f'Błąd podczas zapisywania zmian: {str(e)}')
    
    # Get all markets and industries for dropdowns
    markets = Market.objects.all().order_by('name')
    industries = Industry.objects.all().order_by('name')
    
    # Prepare keywords for display
    keywords_str = ', '.join(company.keywords) if company.keywords else ''
    
    context = {
        'company': company,
        'markets': markets,
        'industries': industries,
        'keywords_str': keywords_str,
    }
    
    return render(request, 'management/company_edit.html', context)


@staff_member_required
@require_POST
def company_delete(request, symbol):
    """Soft delete spółki"""
    company = get_object_or_404(StockSymbol, symbol=symbol)
    
    # Sprawdź czy faktycznie chcemy usunąć
    if request.POST.get('confirm_delete') != 'yes':
        messages.error(request, 'Usuwanie spółki musi zostać potwierdzone.')
        return redirect('users:company_edit', symbol=symbol)
    
    try:
        # Soft delete
        company.delete()  # To wywoła soft delete z modelu
        messages.success(request, f'Spółka {company.symbol} została usunięta pomyślnie.')
        return redirect('users:companies_list')
    except Exception as e:
        messages.error(request, f'Błąd podczas usuwania spółki: {str(e)}')
        return redirect('users:company_edit', symbol=symbol)


@login_required
def company_intraday(request, symbol, date):
    """Dane intraday dla spółki z konkretnego dnia"""
    from datetime import datetime
    from django.http import Http404
    
    company = get_object_or_404(StockSymbol, symbol=symbol)
    
    # Parse date parameter
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise Http404("Invalid date format")
    
    # Get all intraday data for this date
    intraday_data = []
    if StockData:
        intraday_data = list(StockData.objects.filter(
            stock=company,
            data_timestamp__date=target_date
        ).order_by('data_timestamp'))
    
    # Get trading session for this date
    trading_session = None
    try:
        trading_session = TradingSession.objects.get(date=target_date)
    except TradingSession.DoesNotExist:
        pass
    
    # Calculate statistics for the day
    day_stats = {
        'total_records': len(intraday_data),
        'first_record': intraday_data[0].data_timestamp if intraday_data else None,
        'last_record': intraday_data[-1].data_timestamp if intraday_data else None,
        'price_range': None,
        'volume_total': 0
    }
    
    if intraday_data:
        prices = [data.close_price for data in intraday_data if data.close_price]
        if prices:
            day_stats['price_range'] = {
                'min': min(prices),
                'max': max(prices),
                'open': intraday_data[0].open_price or intraday_data[0].close_price,
                'close': intraday_data[-1].close_price
            }
        
        volumes = [data.volume for data in intraday_data if data.volume]
        if volumes:
            day_stats['volume_total'] = sum(volumes)
    
    context = {
        'company': company,
        'target_date': target_date,
        'intraday_data': intraday_data,
        'trading_session': trading_session,
        'day_stats': day_stats,
    }
    
    return render(request, 'management/company_intraday.html', context)


@login_required
@staff_member_required
def scrapers_list(request):
    """Lista scraperów i harmonogramów"""
    from django.utils import timezone
    from datetime import timedelta
    from apps.core.models import ScrapingSchedule, ScrapingExecution
    
    # Use select_related and prefetch_related for better performance
    schedules = ScrapingSchedule.objects.prefetch_related('executions').all().order_by('-is_active', 'name')
    sources = ScrapingSource.objects.all().order_by('name')
    
    # Get recent executions and format them as logs for the template
    recent_executions = ScrapingExecution.objects.select_related('schedule').order_by('-started_at')[:20]
    executions = []
    
    for execution in recent_executions:
        # Format execution as log entry with enhanced details
        duration_info = ""
        if execution.completed_at:
            duration = execution.completed_at - execution.started_at
            if duration.total_seconds() > 60:
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                duration_info = f" (czas: {minutes}m {seconds}s)"
            else:
                duration_info = f" (czas: {duration.total_seconds():.1f}s)"
        
        if execution.success:
            level = 'SUCCESS'
            message = f"Scraper {execution.schedule.name} zakończony pomyślnie{duration_info}"
            
            # Enhanced message based on scraper type and results
            if execution.items_processed > 0:
                message += f" - przetworzono: {execution.items_processed}"
                if execution.items_created > 0:
                    message += f", utworzono: {execution.items_created}"
                if execution.items_updated > 0:
                    message += f", zaktualizowano: {execution.items_updated}"
                    
                # Add specific details for stock prices scraper
                if execution.schedule.scraper_type == 'stock_prices' and execution.execution_details:
                    # Support both old format (with successful/failed fields) and new format
                    execution_details = execution.execution_details
                    successful_count = execution_details.get('successful', 0)
                    failed_count = execution_details.get('failed', 0)
                    
                    # If new format (no successful/failed fields), use processed/updated counts
                    if successful_count == 0 and failed_count == 0:
                        successful_count = execution.items_processed or 0
                        failed_count = 0  # New system doesn't track failed separately
                    
                    # Try to extract stock symbols from command_output
                    command_output = execution_details.get('command_output', '')
                    stock_symbols = []
                    if 'Successful:' in command_output:
                        # Extract stock symbols from output like "Successful: 11 stocks ['11B', 'ALE', ...]"
                        import re
                        match = re.search(r"Successful: \d+ stocks \[(.*?)\]", command_output)
                        if match:
                            # Clean up the stock symbols
                            symbols_str = match.group(1)
                            stock_symbols = [s.strip("' \"") for s in symbols_str.split(',')]
                    
                    if stock_symbols:
                        message += f" | Akcje: {', '.join(stock_symbols[:5])}"
                        if len(stock_symbols) > 5:
                            message += f" i {len(stock_symbols) - 5} innych"
                    elif successful_count > 0:
                        message += f" | {successful_count} akcji przetworzonych"
                        
                    # Only show errors if there are actually failures
                    if failed_count > 0:
                        message += f" | Błędy: {failed_count}"
                        
        else:
            level = 'ERROR'
            message = f"Scraper {execution.schedule.name} zakończony błędem{duration_info}"
            if execution.error_message:
                # Truncate long error messages
                error_msg = execution.error_message[:150] + "..." if len(execution.error_message) > 150 else execution.error_message
                message += f" - {error_msg}"
        
        # Handle running executions
        if not execution.completed_at:
            level = 'INFO' 
            running_time = timezone.now() - execution.started_at
            running_minutes = int(running_time.total_seconds() // 60)
            running_seconds = int(running_time.total_seconds() % 60)
            
            message = f"Scraper {execution.schedule.name} uruchomiony ({running_minutes}m {running_seconds}s temu)"
            if execution.execution_details and 'celery_task_id' in execution.execution_details:
                task_id = execution.execution_details['celery_task_id'][:8]
                message += f" | Task: {task_id}..."
        
        # Prepare enhanced details for modal
        enhanced_details = {
            'execution_pk': execution.pk,
            'schedule_type': execution.schedule.scraper_type,
            'started_at': execution.started_at.isoformat(),
            'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
            'duration': duration_info.strip(' ()') if duration_info else None,
            'success': execution.success,
            'items_processed': execution.items_processed,
            'items_created': execution.items_created,
            'items_updated': execution.items_updated,
            'error_message': execution.error_message,
            'raw_details': execution.execution_details
        }
        
        log_entry = {
            'created_at': execution.started_at,
            'scraper_name': execution.schedule.name,
            'level': level,
            'message': message,
            'details': enhanced_details,
            'execution': execution  # Add full execution object for template access
        }
        executions.append(log_entry)
    
    # Enhanced schedule status with real-time information
    enhanced_schedules = []
    now = timezone.now()
    
    for schedule in schedules:
        # Get latest execution using reverse relationship
        from apps.core.models import ScrapingExecution
        latest_execution = ScrapingExecution.objects.filter(schedule=schedule).first()
        
        # Calculate status
        status = 'unknown'
        status_class = 'secondary'
        
        if not schedule.is_active:
            status = 'inactive'
            status_class = 'secondary'
        elif schedule.should_run_now():
            status = 'due_now'
            status_class = 'warning'
        elif schedule.last_success and (now - schedule.last_success) < timedelta(hours=24):
            status = 'running'
            status_class = 'success'
        elif schedule.failure_count > 0:
            status = 'error'
            status_class = 'danger'
        else:
            status = 'idle'
            status_class = 'info'
        
        # Check if currently executing (running within last 10 minutes without completion)
        is_executing = False
        if latest_execution and not latest_execution.completed_at:
            exec_age = (now - latest_execution.started_at).total_seconds()
            if exec_age < 600:  # 10 minutes
                is_executing = True
                status = 'executing'
                status_class = 'primary'
        
        enhanced_schedule = {
            'schedule': schedule,
            'status': status,
            'status_class': status_class,
            'is_executing': is_executing,
            'latest_execution': latest_execution,
            'next_run_in': None,
            'time_since_last_run': None
        }
        
        # Calculate time until next run
        if schedule.next_run:
            delta = schedule.next_run - now
            if delta.total_seconds() > 0:
                if delta.total_seconds() < 3600:  # Less than 1 hour
                    enhanced_schedule['next_run_in'] = f"{int(delta.total_seconds() / 60)}m"
                else:
                    enhanced_schedule['next_run_in'] = f"{int(delta.total_seconds() / 3600)}h"
        
        # Calculate time since last run
        if schedule.last_run:
            delta = now - schedule.last_run
            if delta.total_seconds() < 3600:  # Less than 1 hour
                enhanced_schedule['time_since_last_run'] = f"{int(delta.total_seconds() / 60)}m ago"
            elif delta.total_seconds() < 86400:  # Less than 1 day
                enhanced_schedule['time_since_last_run'] = f"{int(delta.total_seconds() / 3600)}h ago"
            else:
                enhanced_schedule['time_since_last_run'] = f"{int(delta.total_seconds() / 86400)}d ago"
        
        enhanced_schedules.append(enhanced_schedule)
    
    # Enhanced statistics
    total_schedules = schedules.count()
    active_schedules = schedules.filter(is_active=True).count()
    due_now = sum(1 for s in schedules if s.should_run_now())
    errors_today = ScrapingExecution.objects.filter(
        started_at__date=now.date(), 
        success=False
    ).count()
    
    stats = {
        'total': total_schedules,
        'active': active_schedules,
        'due_now': due_now,
        'errors_today': errors_today,
        'last_run': schedules.filter(last_run__isnull=False).order_by('-last_run').first()
    }
    
    if stats['last_run']:
        stats['last_run'] = stats['last_run'].last_run
    
    context = {
        'schedules': schedules,
        'enhanced_schedules': enhanced_schedules,
        'sources': sources,
        'recent_logs': executions,
        'stats': stats,
    }
    
    return render(request, 'management/scrapers_list.html', context)


@login_required
def data_browser(request):
    """Przeglądarka danych"""
    # Get filter parameters
    symbol_filter = request.GET.get('symbol', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    data_type = request.GET.get('data_type', '')
    
    # Get all symbols for filter dropdown
    symbols = StockSymbol.objects.all().order_by('symbol')
    
    # Initialize querysets
    stock_data = []
    calendar_events = []
    
    # Query stock data if available
    if StockData:
        stock_query = StockData.objects.select_related('stock', 'trading_session').all()
        
        if symbol_filter:
            stock_query = stock_query.filter(stock__symbol__icontains=symbol_filter)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                stock_query = stock_query.filter(trading_session__date__gte=from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                stock_query = stock_query.filter(trading_session__date__lte=to_date)
            except ValueError:
                pass
        
        stock_data = stock_query.order_by('-trading_session__date', 'stock__symbol')[:100]
    
    # Query calendar events if available
    if CompanyCalendarEvent:
        events_query = CompanyCalendarEvent.objects.select_related('stock_symbol').all()
        
        if symbol_filter:
            events_query = events_query.filter(stock_symbol__symbol__icontains=symbol_filter)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                events_query = events_query.filter(event_date__date__gte=from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                events_query = events_query.filter(event_date__date__lte=to_date)
            except ValueError:
                pass
        
        calendar_events = events_query.order_by('-event_date')[:100]
    
    # Basic statistics
    companies_count = StockSymbol.objects.count()
    stock_data_count = StockData.objects.count() if StockData else 0
    events_count = CompanyCalendarEvent.objects.count() if CompanyCalendarEvent else 0
    
    stats = {
        'companies_count': companies_count,
        'stock_data_count': stock_data_count,
        'events_count': events_count,
        'last_update': timezone.now() - timedelta(hours=1),  # Mock for now
    }
    
    # Analysis data
    analysis_data = {
        'stock_summary': None,
        'daily_activity': None,
        'top_companies': symbols[:10]
    }
    
    context = {
        'symbols': symbols,
        'stock_data': stock_data,
        'calendar_events': calendar_events,
        'stats': stats,
        'analysis_data': analysis_data,
        'selected_symbol': symbol_filter,
        'date_from': date_from,
        'date_to': date_to,
        'data_type': data_type,
        'today': timezone.now().date(),
        'page_obj': None,
    }
    
    return render(request, 'management/data_browser.html', context)


@login_required  
@require_POST
def data_browser_refresh(request):
    """Refresh data browser statistics via AJAX"""
    try:
        # Basic statistics
        companies_count = StockSymbol.objects.count()
        stock_data_count = StockData.objects.count() if StockData else 0
        events_count = CompanyCalendarEvent.objects.count() if CompanyCalendarEvent else 0
        
        # Get latest data timestamp
        last_update = timezone.now()
        if StockData:
            latest_stock_data = StockData.objects.order_by('-created_at').first()
            if latest_stock_data:
                last_update = latest_stock_data.created_at
        
        stats = {
            'companies_count': companies_count,
            'stock_data_count': stock_data_count,
            'events_count': events_count,
            'last_update': last_update.isoformat(),
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'message': 'Statystyki zostały odświeżone'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST  
def export_data(request):
    """Eksport danych"""
    if not hasattr(request.user, 'can_export_data') or not request.user.can_export_data:
        messages.error(request, 'Nie masz uprawnień do eksportu danych')
        return redirect('/users/management/data/')
        
    # Mock export functionality
    messages.info(request, 'Funkcja eksportu będzie dostępna wkrótce')
    return redirect('/users/management/data/')


@login_required
@staff_member_required
def system_status(request):
    """Dashboard statusu systemu"""
    today = timezone.now().date()
    
    # System health checks
    system_status = {
        'overall_status': 'healthy',
        'database_status': 'healthy',
        'scrapers_status': 'healthy',
        'data_freshness': 'fresh',
        'online_users': 1,  # Mock data
    }
    
    # Main statistics
    monitored_companies = StockSymbol.objects.filter(is_monitored=True).count()
    total_companies = StockSymbol.objects.count()
    
    stats = {
        'monitored_companies': monitored_companies,
        'total_companies': total_companies,
        'todays_data': 0,  # Will be populated when models are available
        'todays_events': 0,  # Will be populated when models are available
        'last_update': timezone.now() - timedelta(minutes=30),  # Mock
    }
    
    # Performance data (mock)
    performance = {
        'cpu_usage': 25,
        'memory_usage': 45,
        'disk_usage': 60,
    }
    
    # Database stats (mock)
    db_stats = {
        'size': '1.2 GB',
        'connections': 12,
        'queries_per_minute': 150,
        'avg_response_time': 45,
    }
    
    # Recent activities (mock)
    recent_activity = [
        {
            'type': 'success',
            'title': 'Scraper uruchomiony',
            'description': 'Kalendarz wydarzeń zaktualizowany pomyślnie',
            'timestamp': timezone.now() - timedelta(minutes=15)
        },
        {
            'type': 'info', 
            'title': 'Nowy użytkownik',
            'description': 'Użytkownik zalogował się do systemu',
            'timestamp': timezone.now() - timedelta(hours=1)
        }
    ]
    
    context = {
        'system_status': system_status,
        'stats': stats,
        'performance': performance,
        'db_stats': db_stats,
        'recent_errors': [],  # Empty for now
        'recent_activity': recent_activity,
        'scrapers_detailed': ScrapingSchedule.objects.all()[:10],
    }
    
    return render(request, 'management/system_status.html', context)


# AJAX Views for real-time functionality

@login_required
@csrf_exempt
@require_POST
def toggle_company_monitoring_ajax(request, symbol):
    """Toggle company monitoring status via AJAX"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Authentication required'
        }, status=401)
    
    try:
        company = get_object_or_404(StockSymbol, symbol=symbol)
        company.is_monitored = not company.is_monitored
        company.save()
        
        return JsonResponse({
            'success': True,
            'is_monitored': company.is_monitored,
            'message': f'Monitoring {"włączony" if company.is_monitored else "wyłączony"} dla {company.symbol}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def run_scraper_ajax(request, scraper_id):
    """Run scraper manually via AJAX"""
    try:
        from apps.core.scheduler_service import ScrapingScheduler
        
        schedule = get_object_or_404(ScrapingSchedule, id=scraper_id)
        
        # Create scheduler and force synchronous execution for immediate feedback
        scheduler = ScrapingScheduler(use_celery=False)
        execution = scheduler.execute_schedule(schedule, use_celery=False)
        
        if execution.success:
            return JsonResponse({
                'success': True,
                'message': f'Scraper {schedule.name} wykonany pomyślnie',
                'execution_id': execution.pk,
                'items_processed': execution.items_processed,
                'items_created': execution.items_created,
                'items_updated': execution.items_updated
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Błąd podczas wykonywania scrapera: {execution.error_message}',
                'execution_id': execution.pk,
                'error': execution.error_message
            })
        
    except Exception as e:
        logger.error(f"Error running scraper {scraper_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def toggle_scraper_ajax(request, scraper_id):
    """Toggle scraper active status via AJAX"""
    try:
        schedule = get_object_or_404(ScrapingSchedule, id=scraper_id)
        schedule.is_active = not schedule.is_active
        schedule.save()
        
        return JsonResponse({
            'success': True,
            'is_active': schedule.is_active,
            'message': f'Scraper {schedule.name} {"aktywowany" if schedule.is_active else "dezaktywowany"}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def start_all_scrapers_ajax(request):
    """Start all active scrapers via AJAX"""
    try:
        from apps.core.scheduler_service import ScrapingScheduler
        
        scheduler = ScrapingScheduler()  # Use async mode for mass execution
        due_schedules = scheduler.get_due_schedules()
        started_count = 0
        
        if not due_schedules:
            # If no schedules are due, get all active ones
            active_schedules = ScrapingSchedule.objects.filter(is_active=True)
            if active_schedules.count() == 0:
                return JsonResponse({
                    'success': False,
                    'message': 'Brak aktywnych scraperów do uruchomienia'
                })
            
            # Launch async execution for all active schedules
            for schedule in active_schedules[:5]:  # Limit to prevent server overload
                try:
                    execution = scheduler.execute_schedule(schedule, use_celery=True)  # Force async
                    started_count += 1
                except Exception as e:
                    logger.error(f"Error executing schedule {schedule.name}: {e}")
        else:
            # Run due schedules in parallel
            executions = scheduler.run_due_schedules(use_async=True)
            started_count = len(due_schedules)  # Count due schedules, not returned executions
        
        message = f'Uruchomiono {started_count} scraperów w trybie równoległym'
        if scheduler.celery_available:
            message += ' (Celery - zadania wykonują się w tle)'
        else:
            message += ' (synchronicznie)'
            
        return JsonResponse({
            'success': True,
            'message': message,
            'started_count': started_count,
            'async_mode': scheduler.celery_available
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def stop_all_scrapers_ajax(request):
    """Stop all running scrapers via AJAX"""
    try:
        # Here you would implement logic to stop all scrapers
        # For now, we'll just return a success message
        stopped_count = ScrapingSchedule.objects.filter(is_active=True).count()
        
        return JsonResponse({
            'success': True,
            'message': f'Zatrzymano {stopped_count} scraperów',
            'stopped_count': stopped_count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def test_source_ajax(request, source_id):
    """Test scraping source via AJAX"""
    try:
        import requests
        from django.utils import timezone
        
        source = get_object_or_404(ScrapingSource, id=source_id)
        
        # Test connection to the source
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(source.base_url, headers=headers, timeout=10)
            response_time = response.elapsed.total_seconds()
            
            if response.status_code == 200:
                # Update source last_successful_scrape timestamp
                source.record_successful_request()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Test źródła {source.name} zakończony pomyślnie',
                    'status_code': response.status_code,
                    'response_time': f"{response_time:.2f}s",
                    'content_length': len(response.content)
                })
            else:
                source.record_failed_request(f'HTTP {response.status_code}')
                return JsonResponse({
                    'success': False,
                    'message': f'Błąd połączenia: HTTP {response.status_code}',
                    'status_code': response.status_code,
                    'response_time': f"{response_time:.2f}s"
                })
                
        except requests.exceptions.Timeout:
            source.record_failed_request('Connection timeout')
            return JsonResponse({
                'success': False,
                'message': 'Przekroczono limit czasu (timeout)',
                'error': 'timeout'
            })
        except requests.exceptions.ConnectionError:
            source.record_failed_request('Connection error')
            return JsonResponse({
                'success': False,
                'message': 'Błąd połączenia z serwerem',
                'error': 'connection_error'
            })
        except Exception as e:
            source.record_failed_request(str(e))
            return JsonResponse({
                'success': False,
                'message': f'Błąd podczas testowania: {str(e)}',
                'error': str(e)
            })
            
    except Exception as e:
        logger.error(f"Error testing source {source_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def run_stock_scraper_ajax(request):
    """Manually run stock price scraper via AJAX"""
    try:
        from django.core.management import call_command
        from io import StringIO
        import sys
        from django.utils import timezone
        
        # Capture command output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        start_time = timezone.now()
        
        try:
            # Run stock data collection
            call_command('collect_stock_data', '--all')
            output = captured_output.getvalue()
            
            # Parse results
            successful = 0
            failed = 0
            lines = output.split('\n')
            
            for line in lines:
                if "Data collection completed:" in line:
                    try:
                        parts = line.split(':')[1].strip()
                        if '/' in parts:
                            successful = int(parts.split('/')[0])
                    except:
                        pass
                elif "Successful:" in line and "stocks" in line:
                    try:
                        parts = line.split(':')[1].strip()
                        if parts and parts[0].isdigit():
                            successful = int(parts.split()[0])
                    except:
                        pass
                elif "Failed:" in line and "stocks" in line:
                    try:
                        parts = line.split(':')[1].strip()
                        if parts and parts[0].isdigit():
                            failed = int(parts.split()[0])
                    except:
                        pass
            
            duration = (timezone.now() - start_time).total_seconds()
            
            return JsonResponse({
                'success': True,
                'message': f'Stock scraper executed successfully: {successful} successful, {failed} failed',
                'successful': successful,
                'failed': failed,
                'duration': f'{duration:.1f}s',
                'output': output[:500] if len(output) > 500 else output
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Command execution failed: {str(e)}',
                'output': captured_output.getvalue()[:500]
            })
        finally:
            sys.stdout = old_stdout
            
    except Exception as e:
        logger.error(f"Error running stock scraper: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def refresh_logs_ajax(request):
    """Refresh logs via AJAX for real-time updates"""
    try:
        from apps.core.models import ScrapingExecution
        from django.utils import timezone
        
        # Get recent executions and format them using the same logic as scrapers_list
        recent_executions = ScrapingExecution.objects.select_related('schedule').order_by('-started_at')[:20]
        logs = []
        
        for execution in recent_executions:
            # Use the same enhanced formatting logic as in scrapers_list
            duration_info = ""
            if execution.completed_at:
                duration = execution.completed_at - execution.started_at
                if duration.total_seconds() > 60:
                    minutes = int(duration.total_seconds() // 60)
                    seconds = int(duration.total_seconds() % 60)
                    duration_info = f" (czas: {minutes}m {seconds}s)"
                else:
                    duration_info = f" (czas: {duration.total_seconds():.1f}s)"
            
            if execution.success:
                level = 'SUCCESS'
                message = f"Scraper {execution.schedule.name} zakończony pomyślnie{duration_info}"
                
                if execution.items_processed > 0:
                    message += f" - przetworzono: {execution.items_processed}"
                    if execution.items_created > 0:
                        message += f", utworzono: {execution.items_created}"
                    if execution.items_updated > 0:
                        message += f", zaktualizowano: {execution.items_updated}"
                        
                # Add specific details for stock prices scraper
                if execution.schedule.scraper_type == 'stock_prices' and execution.execution_details:
                    successful_count = execution.execution_details.get('successful', 0)
                    failed_count = execution.execution_details.get('failed', 0)
                    
                    # Handle new format that uses items_processed instead
                    if successful_count == 0 and failed_count == 0:
                        successful_count = execution.items_processed or 0
                        failed_count = 0
                    
                    # Try to extract stock symbols from command_output
                    command_output = execution.execution_details.get('command_output', '')
                    stock_symbols = []
                    if 'Successful:' in command_output:
                        # Extract stock symbols from output like "Successful: 11 stocks ['11B', 'ALE', ...]"
                        import re
                        match = re.search(r"Successful: \d+ stocks \[(.*?)\]", command_output)
                        if match:
                            # Clean up the stock symbols
                            symbols_str = match.group(1)
                            stock_symbols = [s.strip("' \"") for s in symbols_str.split(',')]
                    
                    if stock_symbols:
                        message += f" | Akcje: {', '.join(stock_symbols[:5])}"
                        if len(stock_symbols) > 5:
                            message += f" i {len(stock_symbols) - 5} innych"
                    elif successful_count > 0:
                        message += f" | {successful_count} akcji przetworzonych"
                        
                    if failed_count > 0:
                        message += f" | Błędy: {failed_count}"
                            
            else:
                level = 'ERROR'
                message = f"Scraper {execution.schedule.name} zakończony błędem{duration_info}"
                if execution.error_message:
                    error_msg = execution.error_message[:150] + "..." if len(execution.error_message) > 150 else execution.error_message
                    message += f" - {error_msg}"
            
            # Handle running executions
            if not execution.completed_at:
                level = 'INFO' 
                running_time = timezone.now() - execution.started_at
                running_minutes = int(running_time.total_seconds() // 60)
                running_seconds = int(running_time.total_seconds() % 60)
                
                message = f"Scraper {execution.schedule.name} uruchomiony ({running_minutes}m {running_seconds}s temu)"
                if execution.execution_details and 'celery_task_id' in execution.execution_details:
                    task_id = execution.execution_details['celery_task_id'][:8]
                    message += f" | Task: {task_id}..."
            
            log_entry = {
                'created_at': execution.started_at.strftime('%d.%m %H:%M:%S'),
                'completed_at': execution.completed_at.strftime('%H:%M:%S') if execution.completed_at else None,
                'scraper_name': execution.schedule.name,
                'scraper_type': execution.schedule.scraper_type,
                'level': level,
                'message': message,
                'items_processed': execution.items_processed,
                'items_created': execution.items_created,
                'items_updated': execution.items_updated,
                'error_message': execution.error_message,
                'successful_count': execution.execution_details.get('successful', 0) if execution.execution_details else 0,
                'is_running': not execution.completed_at,
                'execution_pk': execution.pk
            }
            logs.append(log_entry)
        
        return JsonResponse({
            'success': True,
            'logs': logs
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def import_historical_data(request):
    """Import historical stock data from TXT files"""
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        
        if not files:
            messages.error(request, 'Nie wybrano żadnych plików do importu.')
            return redirect('users:import_historical_data')
        
        # Process files using the management command logic
        from apps.scrapers.management.commands.import_historical_data import Command
        from apps.scrapers.models import ScrapingSource
        from io import StringIO
        import sys
        import tempfile
        import os
        
        # Capture command output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Get or create source
            source, created = ScrapingSource.objects.get_or_create(
                name='historical_import',
                defaults={
                    'source_type': 'other',
                    'base_url': 'file://web-upload',
                    'is_enabled': True
                }
            )
            
            total_processed = 0
            total_created = 0
            total_skipped = 0
            total_errors = 0
            
            command = Command()
            
            for uploaded_file in files:
                # Save uploaded file temporarily with proper encoding
                with tempfile.NamedTemporaryFile(mode='w+b', suffix='.txt', delete=False) as temp_file:
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name
                
                try:
                    # Process the file - pass original filename for symbol extraction
                    original_filename = uploaded_file.name
                    symbol = original_filename.replace('test_data_', '').replace('.txt', '').upper()
                    
                    stats = command.process_file_with_symbol(
                        temp_file_path,
                        source,
                        symbol,
                        dry_run=False,
                        skip_duplicates=True,
                        create_symbols=True
                    )
                    
                    total_processed += stats['processed']
                    total_created += stats['created']
                    total_skipped += stats['skipped']
                    total_errors += stats['errors']
                    
                except Exception as e:
                    total_errors += 1
                    error_msg = f"Error processing {uploaded_file.name}: {str(e)}"
                
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
            
            # Show success message
            if total_errors == 0:
                messages.success(
                    request, 
                    f'Import zakończony pomyślnie! '
                    f'Przetworzono: {total_processed}, '
                    f'Utworzono: {total_created}, '
                    f'Pominięto duplikaty: {total_skipped}'
                )
            else:
                messages.warning(
                    request,
                    f'Import zakończony z błędami. '
                    f'Przetworzono: {total_processed}, '
                    f'Utworzono: {total_created}, '
                    f'Pominięto: {total_skipped}, '
                    f'Błędy: {total_errors}'
                )
        
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f'Błąd podczas importu: {str(e)}'
            messages.error(request, error_msg)
        
        finally:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        return redirect('users:import_historical_data')
    
    # GET request - show import form
    context = {
        'title': 'Import danych historycznych',
    }
    
    return render(request, 'management/import_historical_data.html', context)


@login_required
@staff_member_required
def schedule_details_ajax(request, schedule_id):
    """Get scheduler details via AJAX"""
    try:
        schedule = get_object_or_404(ScrapingSchedule, id=schedule_id)
        
        data = {
            'id': schedule.pk,
            'name': schedule.name,
            'scraper_type': schedule.scraper_type,
            'scraper_type_display': dict(schedule.SCRAPER_TYPES).get(schedule.scraper_type, schedule.scraper_type),
            'frequency_value': schedule.frequency_value,
            'frequency_unit': schedule.frequency_unit,
            'frequency_description': schedule.frequency_description,
            'is_active': schedule.is_active,
            'active_hours_start': schedule.active_hours_start.strftime('%H:%M') if schedule.active_hours_start else '',
            'active_hours_end': schedule.active_hours_end.strftime('%H:%M') if schedule.active_hours_end else '',
            'last_run': schedule.last_run.strftime('%Y-%m-%d %H:%M:%S') if schedule.last_run else 'Nigdy',
            'last_success': schedule.last_success.strftime('%Y-%m-%d %H:%M:%S') if schedule.last_success else 'Nigdy',
            'next_run': schedule.next_run.strftime('%Y-%m-%d %H:%M:%S') if schedule.next_run else 'Brak',
            'created_at': schedule.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': schedule.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'max_retries': schedule.max_retries,
            'retry_delay_minutes': schedule.retry_delay_minutes,
            'timeout_minutes': schedule.timeout_minutes,
            'failure_count': schedule.failure_count,
            'scraper_config': schedule.scraper_config or {},
            'days': {
                'monday': schedule.monday,
                'tuesday': schedule.tuesday,
                'wednesday': schedule.wednesday,
                'thursday': schedule.thursday,
                'friday': schedule.friday,
                'saturday': schedule.saturday,
                'sunday': schedule.sunday,
            },
            'skip_polish_holidays': schedule.skip_polish_holidays,
            'skip_gpw_holidays': schedule.skip_gpw_holidays,
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error getting schedule details for ID {schedule_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@staff_member_required
def update_schedule_ajax(request, schedule_id):
    """Update scheduler settings via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        schedule = get_object_or_404(ScrapingSchedule, id=schedule_id)
        
        # Parse JSON data
        import json
        data = json.loads(request.body)
        
        # Validate and update fields
        if 'name' in data and data['name'].strip():
            schedule.name = data['name'].strip()
        else:
            return JsonResponse({'success': False, 'error': 'Nazwa jest wymagana'})
        
        if 'scraper_type' in data and data['scraper_type'] in dict(schedule.SCRAPER_TYPES):
            schedule.scraper_type = data['scraper_type']
        
        if 'is_active' in data:
            schedule.is_active = bool(data['is_active'])
        
        if 'frequency_value' in data:
            try:
                freq_value = int(data['frequency_value'])
                if 1 <= freq_value <= 1440:
                    schedule.frequency_value = freq_value
                else:
                    return JsonResponse({'success': False, 'error': 'Częstotliwość musi być między 1 a 1440'})
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Nieprawidłowa częstotliwość'})
        
        if 'frequency_unit' in data and data['frequency_unit'] in ['minutes', 'hours', 'days']:
            schedule.frequency_unit = data['frequency_unit']
        
        # Update time fields
        if 'active_hours_start' in data:
            try:
                from datetime import datetime
                start_time = datetime.strptime(data['active_hours_start'], '%H:%M').time()
                schedule.active_hours_start = start_time
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Nieprawidłowy format godziny rozpoczęcia'})
        
        if 'active_hours_end' in data:
            try:
                from datetime import datetime
                end_time = datetime.strptime(data['active_hours_end'], '%H:%M').time()
                schedule.active_hours_end = end_time
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Nieprawidłowy format godziny zakończenia'})
        
        # Update days
        day_fields = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in day_fields:
            if day in data:
                setattr(schedule, day, bool(data[day]))
        
        # Update holiday settings
        if 'skip_polish_holidays' in data:
            schedule.skip_polish_holidays = bool(data['skip_polish_holidays'])
        
        if 'skip_gpw_holidays' in data:
            schedule.skip_gpw_holidays = bool(data['skip_gpw_holidays'])
        
        # Update technical settings
        if 'max_retries' in data:
            try:
                retries = int(data['max_retries'])
                if 0 <= retries <= 10:
                    schedule.max_retries = retries
                else:
                    return JsonResponse({'success': False, 'error': 'Max powtórzeń musi być między 0 a 10'})
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Nieprawidłowa wartość max powtórzeń'})
        
        if 'retry_delay_minutes' in data:
            try:
                delay = int(data['retry_delay_minutes'])
                if 1 <= delay <= 60:
                    schedule.retry_delay_minutes = delay
                else:
                    return JsonResponse({'success': False, 'error': 'Opóźnienie musi być między 1 a 60 minut'})
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Nieprawidłowa wartość opóźnienia'})
        
        if 'timeout_minutes' in data:
            try:
                timeout = int(data['timeout_minutes'])
                if 1 <= timeout <= 120:
                    schedule.timeout_minutes = timeout
                else:
                    return JsonResponse({'success': False, 'error': 'Timeout musi być między 1 a 120 minut'})
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Nieprawidłowa wartość timeout'})
        
        # Save changes
        schedule.save()
        
        # Recalculate next run time based on new settings
        schedule.calculate_next_run()
        
        logger.info(f"Schedule {schedule.name} (ID: {schedule_id}) updated by user {request.user.username}. Next run: {schedule.next_run}")
        
        return JsonResponse({
            'success': True, 
            'message': f'Scheduler "{schedule.name}" został zaktualizowany',
            'data': {
                'id': schedule.pk,
                'name': schedule.name,
                'is_active': schedule.is_active,
                'frequency_description': schedule.frequency_description,
                'next_run': schedule.next_run.strftime('%Y-%m-%d %H:%M:%S') if schedule.next_run else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating schedule ID {schedule_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
