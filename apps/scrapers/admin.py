from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.utils import timezone
from datetime import timedelta
import time
import logging
from .models import (
    ScrapingSource, ScrapingJob, StockData, ScrapingLog, 
    CompanyCalendarEvent, EventDateChange
)

logger = logging.getLogger(__name__)


@admin.register(ScrapingSource)
class ScrapingSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'base_url', 'is_active']
    list_filter = ['source_type', 'is_active']
    search_fields = ['name', 'base_url']


@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    list_display = ['name', 'job_type', 'source', 'status', 'last_run_time', 'next_run_time']
    list_filter = ['job_type', 'status', 'source', 'is_scheduled']
    search_fields = ['name', 'source__name']
    ordering = ['-next_run_time']


@admin.register(StockData)
class StockDataAdmin(admin.ModelAdmin):
    list_display = ['stock', 'data_timestamp', 'close_price', 'volume', 'source']
    list_filter = ['data_timestamp', 'source', 'is_validated']
    search_fields = ['stock__symbol']
    ordering = ['-data_timestamp']
    readonly_fields = ['scraped_at']


@admin.register(ScrapingLog)
class ScrapingLogAdmin(admin.ModelAdmin):
    list_display = ['source', 'level', 'timestamp', 'message']
    list_filter = ['level', 'source', 'timestamp']
    search_fields = ['message']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']


@admin.register(EventDateChange)
class EventDateChangeAdmin(admin.ModelAdmin):
    list_display = ['event', 'change_type', 'old_date', 'new_date', 'sentiment_impact', 'detected_at']
    list_filter = ['change_type', 'sentiment_impact', 'detected_at']
    search_fields = ['event__title', 'event__stock_symbol__symbol']
    ordering = ['-detected_at']
    readonly_fields = ['detected_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event__stock_symbol')


@admin.register(CompanyCalendarEvent)
class CompanyCalendarEventAdmin(admin.ModelAdmin):
    list_display = [
        'stock_symbol', 'title', 'event_type', 'event_date', 'impact_level',
        'date_changes_indicator', 'is_confirmed', 'is_upcoming'
    ]
    list_filter = [
        'event_type', 'impact_level', 'is_confirmed', 
        'event_date', 'date_changes_count'
    ]
    search_fields = ['title', 'stock_symbol__symbol', 'description']
    ordering = ['event_date']
    readonly_fields = ['created_at', 'updated_at', 'date_changes_count', 'last_date_change']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('stock_symbol', 'title', 'description', 'event_type')
        }),
        ('Date Information', {
            'fields': ('event_date', 'original_date', 'announcement_date', 'date_changes_count', 'last_date_change')
        }),
        ('Market Impact', {
            'fields': ('impact_level', 'is_confirmed')
        }),
        ('Financial Details', {
            'fields': ('dividend_amount', 'currency', 'estimated_eps', 'actual_eps'),
            'classes': ('collapse',)
        }),
        ('Price Impact', {
            'fields': ('pre_event_price', 'post_event_price', 'price_impact_percent'),
            'classes': ('collapse',)
        }),
        ('Source & Metadata', {
            'fields': ('source_url', 'source_name', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def date_changes_indicator(self, obj):
        if obj.date_changes_count > 0:
            return mark_safe(f'<span style="color: red;">🔄 {obj.date_changes_count} changes</span>')
        return mark_safe('<span style="color: green;">✅ No changes</span>')
    
    def is_upcoming(self, obj):
        return obj.is_upcoming
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('stock_symbol')
    
    # Custom admin URLs for calendar scraping
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('scrape-calendar/', self.admin_site.admin_view(self.scrape_calendar_view), name='scrapers-calendar-scrape'),
        ]
        return custom_urls + urls
    
    def scrape_calendar_view(self, request):
        """Custom admin view for calendar scraping with date range selection."""
        if request.method == 'POST':
            # Get form data
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            job_name = request.POST.get('job_name', 'Admin Calendar Scrape')
            
            try:
                # Convert dates
                start_dt = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
                
                # Validation
                if end_dt <= start_dt:
                    messages.error(request, 'End date must be after start date!')
                    return redirect(request.get_full_path())
                
                if (end_dt - start_dt).days > 180:
                    messages.error(request, 'Date range cannot exceed 6 months!')
                    return redirect(request.get_full_path())
                
                # Import and run scraper
                from scraper.calendar.bankier_calendar_scraper import BankierCalendarScraper
                scraper = BankierCalendarScraper()
                
                # Process week by week
                events_created = 0
                events_updated = 0
                date_changes_detected = 0
                weeks_processed = 0
                
                current_date = start_dt
                while current_date <= end_dt:
                    try:
                        # Scrape weekly data
                        result = scraper.scrape_and_save_weekly_calendar(
                            timezone.datetime.combine(current_date, timezone.datetime.min.time())
                        )
                        
                        events_created += result.get('events_created', 0)
                        events_updated += result.get('events_updated', 0) 
                        date_changes_detected += result.get('date_changes_detected', 0)
                        weeks_processed += 1
                        
                        # Move to next week
                        current_date += timedelta(days=7)
                        
                        # Rate limiting
                        time.sleep(1)
                        
                    except Exception as week_error:
                        logger.error(f"Error processing week {current_date}: {week_error}")
                        continue
                
                # Success message
                messages.success(
                    request, 
                    f'✅ Calendar scraping completed! '
                    f'Created: {events_created}, Updated: {events_updated}, '
                    f'Date changes: {date_changes_detected}, Weeks: {weeks_processed}'
                )
                
            except Exception as e:
                logger.error(f"Calendar scraping error: {e}")
                messages.error(request, f'❌ Scraping failed: {str(e)}')
            
            return redirect('..')
        
        # Prepare context data
        context = {
            'title': 'Scrape Calendar Events',
            'opts': self.model._meta,
            'total_events': CompanyCalendarEvent.objects.count(),
            'future_events': CompanyCalendarEvent.objects.filter(event_date__gte=timezone.now()).count(),
            'date_changes': EventDateChange.objects.count(),
            'today': timezone.now().date(),
            'six_months_later': (timezone.now() + timedelta(days=180)).date(),
        }
        
        return render(request, 'admin/scrapers/scrape_calendar.html', context)
