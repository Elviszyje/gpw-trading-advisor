from django.contrib import admin
from .models import StockSymbol, TradingSession


@admin.register(StockSymbol)
class StockSymbolAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'bankier_symbol', 'sector', 'is_monitored', 'is_active', 'created_at']
    list_filter = ['sector', 'is_monitored', 'is_active']
    search_fields = ['symbol', 'name', 'bankier_symbol']
    ordering = ['symbol']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('symbol', 'name', 'sector')
        }),
        ('Scraping Configuration', {
            'fields': ('bankier_symbol',),
            'description': 'Configure symbol mapping for different data sources'
        }),
        ('Settings', {
            'fields': ('is_monitored', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(TradingSession)
class TradingSessionAdmin(admin.ModelAdmin):
    list_display = ['date', 'is_trading_day', 'market_open_time', 'market_close_time', 'is_active']
    list_filter = ['is_trading_day', 'is_active']
    ordering = ['-date']
    readonly_fields = ['created_at', 'updated_at']
