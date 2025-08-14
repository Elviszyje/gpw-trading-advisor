"""
Django Admin Configuration for News and Events
Advanced admin interface with date range selection and change tracking
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Any, Dict, List
import json

from .models import (
    NewsSource, NewsArticleModel, CompanyCalendarEvent, 
    EventDateChange, ESPIReport, CalendarScrapingJob
)
from .forms import CalendarScrapingForm


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_active', 'last_scraped', 'articles_count']
    list_filter = ['type', 'is_active']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'url', 'type', 'is_active')
        }),
        ('Configuration', {
            'fields': ('scraping_config',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('last_scraped', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        })
    )
    
    def articles_count(self, obj):
        return obj.articles.count()
    articles_count.short_description = 'Articles'  # type: ignore


@admin.register(NewsArticleModel)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ['title_short', 'source', 'sentiment', 'market_impact', 'published_date', 'stock_count']
    list_filter = ['sentiment', 'market_impact', 'source', 'is_analyzed', 'published_date']
    search_fields = ['title', 'content']
    filter_horizontal = ['mentioned_stocks']
    readonly_fields = ['scraped_at', 'updated_at', 'analysis_date']
    date_hierarchy = 'published_date'
    
    fieldsets = (
        ('Article Content', {
            'fields': ('title', 'content', 'url', 'source')
        }),
        ('Stock Associations', {
            'fields': ('primary_stock', 'mentioned_stocks')
        }),
        ('Analysis', {
            'fields': ('sentiment', 'sentiment_score', 'market_impact', 'impact_score', 'is_analyzed', 'analysis_date')
        }),
        ('Metadata', {
            'fields': ('keywords', 'tags', 'published_date', 'scraped_at', 'updated_at'),
            'classes': ('collapse',),
        })
    )
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'  # type: ignore
    
    def stock_count(self, obj):
        return obj.mentioned_stocks.count()
    stock_count.short_description = 'Stocks'  # type: ignore


@admin.register(CompanyCalendarEvent)
class CompanyCalendarEventAdmin(admin.ModelAdmin):
    list_display = ['stock_symbol', 'title_short', 'event_type', 'event_date', 'date_changes_indicator', 'market_impact', 'is_confirmed']
    list_filter = ['event_type', 'market_impact', 'is_confirmed', 'is_completed', 'event_date']
    search_fields = ['title', 'description', 'stock__symbol', 'stock__company_name']
    readonly_fields = ['original_date', 'date_changes_count', 'created_at', 'updated_at', 'last_verified']
    date_hierarchy = 'event_date'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('stock', 'title', 'description', 'event_type')
        }),
        ('Date Tracking', {
            'fields': ('event_date', 'original_date', 'date_changes_count'),
            'description': 'Track date changes for investor sentiment analysis'
        }),
        ('Market Impact', {
            'fields': ('market_impact', 'impact_score', 'is_confirmed', 'is_completed')
        }),
        ('Financial Data', {
            'fields': ('dividend_amount', 'dividend_currency'),
            'classes': ('collapse',),
        }),
        ('Source & Metadata', {
            'fields': ('source_url', 'source_name', 'created_at', 'updated_at', 'last_verified'),
            'classes': ('collapse',),
        })
    )
    
    def stock_symbol(self, obj):
        return obj.stock.symbol
    stock_symbol.short_description = 'Stock'  # type: ignore
    stock_symbol.admin_order_field = 'stock__symbol'  # type: ignore
    
    def title_short(self, obj):
        return obj.title[:40] + '...' if len(obj.title) > 40 else obj.title
    title_short.short_description = 'Title'  # type: ignore
    
    def date_changes_indicator(self, obj):
        if obj.date_changes_count > 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ {} changes</span>',
                obj.date_changes_count
            )
        return format_html('<span style="color: green;">✓ Stable</span>')
    date_changes_indicator.short_description = 'Date Changes'  # type: ignore
    
    actions = ['mark_as_confirmed', 'mark_as_completed', 'refresh_from_source']
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(is_confirmed=True)
        self.message_user(request, f'{updated} events marked as confirmed.')
    mark_as_confirmed.short_description = 'Mark selected events as confirmed'  # type: ignore
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(is_completed=True)
        self.message_user(request, f'{updated} events marked as completed.')
    mark_as_completed.short_description = 'Mark selected events as completed'  # type: ignore


@admin.register(EventDateChange)
class EventDateChangeAdmin(admin.ModelAdmin):
    list_display = ['event_title', 'stock_symbol', 'change_type', 'old_date', 'new_date', 'days_diff', 'sentiment_impact', 'detected_at']
    list_filter = ['change_type', 'sentiment_impact', 'detected_at']
    search_fields = ['event__title', 'event__stock__symbol', 'change_reason']
    readonly_fields = ['detected_at']
    date_hierarchy = 'detected_at'
    
    fieldsets = (
        ('Change Information', {
            'fields': ('event', 'old_date', 'new_date', 'change_type')
        }),
        ('Impact Analysis', {
            'fields': ('sentiment_impact', 'change_reason')
        }),
        ('Metadata', {
            'fields': ('source_url', 'detected_at'),
            'classes': ('collapse',),
        })
    )
    
    def event_title(self, obj):
        return obj.event.title[:40] + '...' if len(obj.event.title) > 40 else obj.event.title
    event_title.short_description = 'Event'  # type: ignore
    
    def stock_symbol(self, obj):
        return obj.event.stock.symbol
    stock_symbol.short_description = 'Stock'  # type: ignore
    
    def days_diff(self, obj):
        diff = obj.days_difference()
        if diff is None:
            return 'N/A'
        if diff > 0:
            return format_html('<span style="color: red;">+{} days</span>', diff)
        elif diff < 0:
            return format_html('<span style="color: orange;">{} days</span>', diff)
        return '0 days'
    days_diff.short_description = 'Days Change'  # type: ignore


@admin.register(ESPIReport)
class ESPIReportAdmin(admin.ModelAdmin):
    list_display = ['stock_symbol', 'report_number', 'title_short', 'report_type', 'importance', 'sentiment', 'publication_date']
    list_filter = ['report_type', 'importance', 'sentiment', 'publication_date']
    search_fields = ['title', 'content', 'report_number', 'stock__symbol']
    readonly_fields = ['scraped_at', 'updated_at']
    date_hierarchy = 'publication_date'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('stock', 'report_number', 'title', 'content')
        }),
        ('Classification', {
            'fields': ('report_type', 'importance', 'sentiment', 'market_impact_score')
        }),
        ('Source', {
            'fields': ('source_url', 'attachment_urls')
        }),
        ('Analysis', {
            'fields': ('keywords',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('publication_date', 'scraped_at', 'updated_at'),
            'classes': ('collapse',),
        })
    )
    
    def stock_symbol(self, obj):
        return obj.stock.symbol
    stock_symbol.short_description = 'Stock'  # type: ignore
    stock_symbol.admin_order_field = 'stock__symbol'  # type: ignore
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'  # type: ignore


@admin.register(CalendarScrapingJob)
class CalendarScrapingJobAdmin(admin.ModelAdmin):
    list_display = ['name', 'date_range', 'status', 'events_summary', 'success_rate_display', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['started_at', 'completed_at', 'duration_display', 'success_rate_display', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Job Configuration', {
            'fields': ('name', 'description', 'start_date', 'end_date')
        }),
        ('Source Configuration', {
            'fields': ('source_urls', 'scraping_config'),
            'classes': ('collapse',),
        }),
        ('Execution Status', {
            'fields': ('status', 'started_at', 'completed_at', 'duration_display')
        }),
        ('Results', {
            'fields': ('events_found', 'events_created', 'events_updated', 'date_changes_detected', 'success_rate_display')
        }),
        ('Logs & Errors', {
            'fields': ('logs', 'error_message'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        })
    )
    
    def date_range(self, obj):
        return f"{obj.start_date} to {obj.end_date}"
    date_range.short_description = 'Date Range'  # type: ignore
    
    def events_summary(self, obj):
        return f"{obj.events_created + obj.events_updated}/{obj.events_found}"
    events_summary.short_description = 'Events (Success/Total)'  # type: ignore
    
    def success_rate_display(self, obj):
        rate = obj.success_rate() * 100
        if rate >= 90:
            color = 'green'
        elif rate >= 70:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)
    success_rate_display.short_description = 'Success Rate'  # type: ignore
    
    def duration_display(self, obj):
        duration = obj.duration()
        return duration if duration else 'N/A'
    duration_display.short_description = 'Duration'  # type: ignore
    
    # Custom admin URLs
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('scrape-calendar/', self.admin_site.admin_view(self.scrape_calendar_view), name='scrape_calendar'),
        ]
        return custom_urls + urls
    
    def scrape_calendar_view(self, request):
        """Custom view for scraping calendar with date range selection"""
        if request.method == 'POST':
            form = CalendarScrapingForm(request.POST)
            if form.is_valid():
                # Create scraping job
                job = CalendarScrapingJob.objects.create(
                    name=form.cleaned_data['name'],
                    description=form.cleaned_data['description'],
                    start_date=form.cleaned_data['start_date'],
                    end_date=form.cleaned_data['end_date'],
                    source_urls=form.cleaned_data['source_urls'],
                    scraping_config=form.cleaned_data.get('scraping_config', {}),
                    created_by=request.user
                )
                
                # TODO: Trigger async scraping task
                messages.success(request, f'Scraping job "{job.name}" created successfully!')
                return redirect('admin:news_calendarscrapingjob_changelist')
        else:
            # Pre-fill with sensible defaults
            form = CalendarScrapingForm(initial={
                'name': f'Calendar Scrape {timezone.now().strftime("%Y-%m-%d")}',
                'start_date': timezone.now().date(),
                'end_date': timezone.now().date() + timedelta(weeks=12),  # 3 months ahead
                'source_urls': ['https://www.bankier.pl/gielda/kalendarium/'],
            })
        
        context = {
            'title': 'Scrape Calendar Events',
            'form': form,
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        return render(request, 'admin/news/scrape_calendar.html', context)


# Add custom admin site configuration
class NewsEventsAdminConfig:
    """Configuration for news and events admin interface"""
    
    @staticmethod
    def get_dashboard_stats():
        """Get dashboard statistics for admin"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        return {
            'total_events': CompanyCalendarEvent.objects.count(),
            'future_events': CompanyCalendarEvent.objects.filter(event_date__gte=today).count(),
            'events_this_week': CompanyCalendarEvent.objects.filter(
                event_date__range=[today, today + timedelta(days=7)]
            ).count(),
            'date_changes_this_week': EventDateChange.objects.filter(
                detected_at__gte=week_ago
            ).count(),
            'high_impact_events': CompanyCalendarEvent.objects.filter(
                market_impact='high',
                event_date__gte=today
            ).count(),
            'unconfirmed_events': CompanyCalendarEvent.objects.filter(
                is_confirmed=False,
                event_date__gte=today
            ).count(),
        }


# Customize admin site
admin.site.site_header = 'GPW Trading Advisor Administration'
admin.site.site_title = 'GPW Admin'
admin.site.index_title = 'Trading Intelligence Dashboard'
