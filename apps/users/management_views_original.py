"""
Management interface views for business operations
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import date, timedelta, datetime
import json

from apps.core.models import StockSymbol, ScrapingSchedule, ScrapingExecution
from apps.scrapers.models import ScrapingSource, ScrapingJob

# Try to import optional models that may not exist
try:
    from apps.core.models import StockData
except ImportError:
    StockData = None

try:
    from apps.news.models import CompanyCalendarEvent
except ImportError:
    CompanyCalendarEvent = None

try:
    from apps.scrapers.models import ScrapingLog
except ImportError:
    ScrapingLog = None


@login_required
def companies_list(request):
    """Lista wszystkich spółek"""
    search_query = request.GET.get('search', '')
    market_filter = request.GET.get('market', '')
    monitored_filter = request.GET.get('monitored', '')
    
    companies = StockSymbol.objects.all()
    
    if search_query:
        companies = companies.filter(
            Q(symbol__icontains=search_query) |
            Q(name__icontains=search_query)
        )
    
    if market_filter:
        companies = companies.filter(market=market_filter)
    
    if monitored_filter == 'true':
        companies = companies.filter(is_monitored=True)
    elif monitored_filter == 'false':
        companies = companies.filter(is_monitored=False)
    
    companies = companies.order_by('symbol')
    
    # Paginacja
    paginator = Paginator(companies, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statystyki
    stats = {
        'total': StockSymbol.objects.count(),
        'monitored': StockSymbol.objects.filter(is_monitored=True).count(),
        'markets': StockSymbol.objects.values('market').distinct().count(),
    }
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'market_filter': market_filter,
        'monitored_filter': monitored_filter,
        'stats': stats,
        'markets': StockSymbol.objects.values_list('market', flat=True).distinct(),
    }
    
    return render(request, 'management/companies_list.html', context)


@login_required
def company_detail(request, symbol):
    """Szczegóły spółki"""
    company = get_object_or_404(StockSymbol, symbol=symbol)
    
    # Get recent stock data if available
    recent_data = []
    if StockData:
        recent_data = StockData.objects.filter(stock=company).order_by('-trading_session__date')[:30]
    
    # Get calendar events if available
    upcoming_events = []
    past_events = []
    if CompanyCalendarEvent:
        upcoming_events = CompanyCalendarEvent.objects.filter(
            stock_symbol=company,
            event_date__gte=timezone.now()
        ).order_by('event_date')[:10]
        
        past_events = CompanyCalendarEvent.objects.filter(
            stock_symbol=company,
            event_date__lt=timezone.now()
        ).order_by('-event_date')[:10]
    
    # Statystyki
    last_data = recent_data[0] if recent_data else None
    stats = {
        'data_points': StockData.objects.filter(stock=company).count() if StockData else 0,
        'calendar_events': CompanyCalendarEvent.objects.filter(stock_symbol=company).count() if CompanyCalendarEvent else 0,
        'last_update': last_data.created_at if last_data and hasattr(last_data, 'created_at') else None,
    }
    
    context = {
        'company': company,
        'recent_data': recent_data,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'stats': stats,
    }
    
    return render(request, 'management/company_detail.html', context)


@login_required 
def scrapers_list(request):
    """Lista scraperów i ich konfiguracji"""
    # Źródła scrapingu
    sources = ScrapingSource.objects.all()
    
    # Zadania scrapingu
    jobs = ScrapingJob.objects.all().order_by('-created_at')
    
    # Harmonogramy
    schedules = ScrapingSchedule.objects.all().order_by('name')
    
    # Ostatnie logi
    recent_logs = ScrapingLog.objects.order_by('-timestamp')[:20]
    
    # Statystyki
    stats = {
        'total_sources': sources.count(),
        'active_jobs': jobs.filter(is_active=True).count(),
        'schedules': schedules.count(),
        'active_schedules': schedules.filter(is_active=True).count(),
        'today_executions': ScrapingLog.objects.filter(
            timestamp__date=timezone.now().date()
        ).count(),
    }
    
    context = {
        'sources': sources,
        'jobs': jobs[:10],  # Ostatnie 10
        'schedules': schedules,
        'recent_logs': recent_logs,
        'stats': stats,
    }
    
    return render(request, 'management/scrapers_list.html', context)


@login_required
def scraper_detail(request, scraper_id):
    """Szczegóły scrapera"""
    schedule = get_object_or_404(ScrapingSchedule, id=scraper_id)
    
    # Logi dla tego scrapera
    logs = ScrapingLog.objects.filter(
        scraper_name__icontains=schedule.name
    ).order_by('-timestamp')[:50]
    
    # Statystyki
    last_7_days = timezone.now() - timedelta(days=7)
    last_log = logs.first()
    stats = {
        'total_runs': logs.count(),
        'success_rate': logs.filter(status='SUCCESS').count() / max(logs.count(), 1) * 100,
        'last_run': last_log.timestamp if last_log else None,
        'recent_failures': logs.filter(
            status='ERROR',
            timestamp__gte=last_7_days
        ).count(),
    }
    
    context = {
        'schedule': schedule,
        'logs': logs,
        'stats': stats,
    }
    
    return render(request, 'management/scraper_detail.html', context)


@login_required
def data_browser(request):
    """Przeglądarka danych ześcrapowanych"""
    date_filter = request.GET.get('date', '')
    symbol_filter = request.GET.get('symbol', '')
    data_type = request.GET.get('type', 'stock_data')
    
    data = None
    
    if data_type == 'stock_data':
        data = StockData.objects.select_related('stock', 'trading_session')
        
        if date_filter:
            try:
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                data = data.filter(trading_session__date=filter_date)
            except ValueError:
                pass
        
        if symbol_filter:
            data = data.filter(stock__symbol__icontains=symbol_filter)
        
        data = data.order_by('-trading_session__date', 'stock__symbol')
        
    elif data_type == 'calendar_events':
        data = CompanyCalendarEvent.objects.select_related('stock_symbol')
        
        if date_filter:
            try:
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                data = data.filter(event_date__date=filter_date)
            except ValueError:
                pass
        
        if symbol_filter:
            data = data.filter(stock_symbol__symbol__icontains=symbol_filter)
        
        data = data.order_by('-event_date')
    
    if data is None:
        data = StockData.objects.none()
    
    # Paginacja
    paginator = Paginator(data, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dostępne symbole dla filtra
    symbols = StockSymbol.objects.values_list('symbol', flat=True).order_by('symbol')
    
    context = {
        'page_obj': page_obj,
        'date_filter': date_filter,
        'symbol_filter': symbol_filter,
        'data_type': data_type,
        'symbols': symbols,
    }
    
    return render(request, 'management/data_browser.html', context)


@login_required
def run_scraper_ajax(request, scraper_id):
    """AJAX endpoint do uruchomienia scrapera"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    schedule = get_object_or_404(ScrapingSchedule, id=scraper_id)
    
    try:
        # Import scheduler service
        from apps.core.scheduler_service import ScrapingScheduler
        
        scheduler = ScrapingScheduler()
        result = scheduler.execute_schedule(schedule)
        
        return JsonResponse({
            'success': True,
            'message': f'Scraper {schedule.name} uruchomiony pomyślnie',
            'result': result
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def toggle_scraper_ajax(request, scraper_id):
    """AJAX endpoint do włączania/wyłączania scrapera"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    schedule = get_object_or_404(ScrapingSchedule, id=scraper_id)
    schedule.is_active = not schedule.is_active
    schedule.save()
    
    return JsonResponse({
        'success': True,
        'is_active': schedule.is_active,
        'message': f'Scraper {schedule.name} {"włączony" if schedule.is_active else "wyłączony"}'
    })


@login_required
def toggle_company_monitoring_ajax(request, symbol):
    """AJAX endpoint do włączania/wyłączania monitorowania spółki"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    company = get_object_or_404(StockSymbol, symbol=symbol)
    company.is_monitored = not company.is_monitored
    company.save()
    
    return JsonResponse({
        'success': True,
        'is_monitored': company.is_monitored,
        'message': f'Monitorowanie {company.symbol} {"włączone" if company.is_monitored else "wyłączone"}'
    })


@login_required
def export_data(request):
    """Eksport danych do CSV/JSON"""
    data_type = request.GET.get('type', 'stock_data')
    format_type = request.GET.get('format', 'csv')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    symbol = request.GET.get('symbol', '')
    
    if not request.user.can_export_data:
        messages.error(request, 'Nie masz uprawnień do eksportu danych')
        return redirect('management:data_browser')
    
    # TODO: Implementacja eksportu
    messages.info(request, 'Funkcja eksportu będzie dostępna wkrótce')
    return redirect('management:data_browser')


@login_required
def system_status(request):
    """Status systemu i statystyki"""
    now = timezone.now()
    today = now.date()
    
    # Statystyki główne
    stats = {
        'companies': {
            'total': StockSymbol.objects.count(),
            'monitored': StockSymbol.objects.filter(is_monitored=True).count(),
            'markets': StockSymbol.objects.values('market').distinct().count(),
        },
        'data': {
            'stock_data_points': StockData.objects.count(),
            'calendar_events': CompanyCalendarEvent.objects.count(),
            'data_today': StockData.objects.filter(created_at__date=today).count(),
        },
        'scrapers': {
            'total_schedules': ScrapingSchedule.objects.count(),
            'active_schedules': ScrapingSchedule.objects.filter(is_active=True).count(),
            'executions_today': ScrapingLog.objects.filter(timestamp__date=today).count(),
            'success_rate_today': _calculate_success_rate(today),
        }
    }
    
    # Ostatnie aktywności
    recent_activities = ScrapingLog.objects.order_by('-timestamp')[:10]
    
    # Nadchodzące harmonogramy
    upcoming_schedules = ScrapingSchedule.objects.filter(
        is_active=True,
        next_run__isnull=False
    ).order_by('next_run')[:5]
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'upcoming_schedules': upcoming_schedules,
    }
    
    return render(request, 'management/system_status.html', context)


def _calculate_success_rate(date):
    """Oblicz wskaźnik sukcesu dla danego dnia"""
    logs = ScrapingLog.objects.filter(timestamp__date=date)
    if not logs.exists():
        return 0
    
    success_count = logs.filter(status='SUCCESS').count()
    return round((success_count / logs.count()) * 100, 1)
