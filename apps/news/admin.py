"""
Django Admin for News App - ONLY for news articles  
ESPI reports admin is in apps/scrapers/
Calendar events admin is in apps/scrapers/
"""
from django.contrib import admin
from .models import NewsSource, NewsArticleModel


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_active', 'last_scraped', 'created_at']
    list_filter = ['type', 'is_active', 'created_at']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at', 'last_scraped']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'url', 'type', 'is_active')
        }),
        ('Configuration', {
            'fields': ('scraping_config',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_scraped', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NewsArticleModel)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ['title_short', 'source', 'primary_stock', 'sentiment', 'market_impact', 'published_date', 'is_analyzed']
    list_filter = ['sentiment', 'market_impact', 'is_analyzed', 'source', 'published_date']
    search_fields = ['title', 'content', 'keywords']
    readonly_fields = ['scraped_at', 'updated_at']
    filter_horizontal = ['mentioned_stocks']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'url', 'source', 'published_date')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Stock Relations', {
            'fields': ('primary_stock', 'mentioned_stocks')
        }),
        ('Analysis', {
            'fields': ('sentiment', 'sentiment_score', 'market_impact', 'impact_score', 'is_analyzed', 'analysis_date')
        }),
        ('Metadata', {
            'fields': ('keywords', 'tags', 'scraped_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def title_short(self, obj):
        return obj.title[:60] + "..." if len(obj.title) > 60 else obj.title
    title_short.short_description = 'Title'  # type: ignore
