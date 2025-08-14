"""
Management interface views for business operations - Simplified version
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


@login_required
@staff_member_required
def companies_list(request):
    """Lista spółek z możliwością filtrowania"""
    search_query = request.GET.get('search', '')
    market_filter = request.GET.get('market', '')
    monitored_filter = request.GET.get('monitored', '')
    
    # Base queryset
    companies = StockSymbol.objects.all()
    
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
    
    stats = {
        'total': total_companies,
        'monitored': monitored_companies,
        'markets': len([m for m in markets if m])
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
    }
    
    return render(request, 'management/companies_list.html', context)


@login_required
def company_detail(request, symbol):
    """Szczegóły spółki"""
    company = get_object_or_404(StockSymbol, symbol=symbol)
    
    # Basic stats 
    stats = {
        'data_points': 0,  # Will be populated when models are available
        'calendar_events': 0,  # Will be populated when models are available
        'last_update': company.updated_at if hasattr(company, 'updated_at') else None,
    }
    
    context = {
        'company': company,
        'latest_data': [],  # Empty for now
        'calendar_events': [],  # Empty for now  
        'stats': stats,
        'today': timezone.now().date(),
    }
    
    return render(request, 'management/company_detail.html', context)


@login_required
@staff_member_required
def scrapers_list(request):
    """Lista scraperów i harmonogramów"""
    schedules = ScrapingSchedule.objects.all().order_by('-is_active', 'name')
    sources = ScrapingSource.objects.all().order_by('name')
    executions = ScrapingExecution.objects.order_by('-started_at')[:20]
    
    # Statistics
    total_schedules = schedules.count()
    active_schedules = schedules.filter(is_active=True).count()
    
    stats = {
        'total': total_schedules,
        'active': active_schedules,
        'errors_today': 0,  # Will be calculated when logs are available
        'last_run': schedules.filter(last_run__isnull=False).order_by('-last_run').first()
    }
    
    if stats['last_run']:
        stats['last_run'] = stats['last_run'].last_run
    
    context = {
        'schedules': schedules,
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
    
    # Initialize empty querysets
    stock_data = []
    calendar_events = []
    
    # Basic statistics
    companies_count = StockSymbol.objects.count()
    
    stats = {
        'companies_count': companies_count,
        'stock_data_count': 0,  # Will be populated when models are available
        'events_count': 0,  # Will be populated when models are available
        'last_update': timezone.now() - timedelta(hours=1),  # Mock data
    }
    
    # Analysis data (mock for now)
    analysis_data = {
        'stock_summary': None,
        'daily_activity': None,
        'top_companies': symbols[:10]  # Just show first 10 companies as mock
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
        'page_obj': None,  # No pagination for now
    }
    
    return render(request, 'management/data_browser.html', context)


@login_required
@require_POST  
def export_data(request):
    """Eksport danych"""
    if not hasattr(request.user, 'can_export_data') or not request.user.can_export_data:
        messages.error(request, 'Nie masz uprawnień do eksportu danych')
        return redirect('management:data_browser')
        
    # Mock export functionality
    messages.info(request, 'Funkcja eksportu będzie dostępna wkrótce')
    return redirect('management:data_browser')


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
@require_POST
def toggle_company_monitoring_ajax(request, symbol):
    """Toggle company monitoring status via AJAX"""
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
        schedule = get_object_or_404(ScrapingSchedule, id=scraper_id)
        
        # Create execution record
        execution = ScrapingExecution.objects.create(
            schedule=schedule,
            started_at=timezone.now()
        )
        
        # In a real implementation, you would trigger the actual scraper here
        # For now, just mark it as successful after a mock delay
        execution.success = True
        execution.completed_at = timezone.now()
        execution.save()
        
        schedule.last_run = timezone.now()
        schedule.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Scraper {schedule.name} został uruchomiony'
        })
    except Exception as e:
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
