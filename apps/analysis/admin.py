from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models import TimeWeightConfiguration

@admin.register(TimeWeightConfiguration)
class TimeWeightConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for Time Weight Configuration management"""
    
    list_display = [
        'name', 
        'trading_style_display', 
        'is_active',
        'half_life_display',
        'weight_distribution',
        'multipliers_display',
        'impact_threshold'
    ]
    
    list_filter = [
        'trading_style',
        'is_active',
        'created_at'
    ]
    
    search_fields = ['name', 'trading_style']
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('name', 'trading_style', 'is_active'),
            'description': 'Basic settings for the time-weighted news analysis configuration'
        }),
        ('Time Decay Settings', {
            'fields': ('half_life_minutes',),
            'description': 'Controls how quickly news loses impact over time (exponential decay)'
        }),
        ('Time Period Weights', {
            'fields': (
                'last_15min_weight',
                'last_1hour_weight', 
                'last_4hour_weight',
                'today_weight'
            ),
            'description': 'Weight distribution across different time periods (must sum to ~1.0)'
        }),
        ('Impact Multipliers', {
            'fields': (
                'breaking_news_multiplier',
                'market_hours_multiplier',
                'pre_market_multiplier'
            ),
            'description': 'Multipliers for different news contexts'
        }),
        ('Analysis Thresholds', {
            'fields': ('min_impact_threshold',),
            'description': 'Minimum impact score required for signal modification'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def trading_style_display(self, obj):
        """Display trading style with color coding"""
        colors = {
            'intraday': '#e74c3c',  # Red
            'swing': '#3498db',     # Blue
            'position': '#2ecc71'   # Green
        }
        color = colors.get(obj.trading_style, '#95a5a6')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_trading_style_display()
        )
    trading_style_display.short_description = 'Trading Style'
    
    def half_life_display(self, obj):
        """Display half-life in readable format"""
        if obj.half_life_minutes < 60:
            return f"{obj.half_life_minutes}min"
        elif obj.half_life_minutes < 1440:
            hours = obj.half_life_minutes / 60
            return f"{hours:.1f}h"
        else:
            days = obj.half_life_minutes / 1440
            return f"{days:.1f}d"
    half_life_display.short_description = 'Half-Life'
    
    def weight_distribution(self, obj):
        """Display weight distribution as percentages"""
        return format_html(
            '<small>15m: {:.0%} | 1h: {:.0%} | 4h: {:.0%} | Today: {:.0%}</small>',
            obj.last_15min_weight,
            obj.last_1hour_weight,
            obj.last_4hour_weight,
            obj.today_weight
        )
    weight_distribution.short_description = 'Weight Distribution'
    
    def multipliers_display(self, obj):
        """Display multipliers"""
        return format_html(
            '<small>Breaking: {:.1f}x | Market: {:.1f}x | Pre: {:.1f}x</small>',
            obj.breaking_news_multiplier,
            obj.market_hours_multiplier,
            obj.pre_market_multiplier
        )
    multipliers_display.short_description = 'Multipliers'
    
    def impact_threshold(self, obj):
        """Display impact threshold"""
        return f"{obj.min_impact_threshold:.3f}"
    impact_threshold.short_description = 'Min Threshold'
    
    def save_model(self, request, obj, form, change):
        """Custom save with validation and messaging"""
        super().save_model(request, obj, form, change)
        
        # Validate weight distribution
        total_weight = (
            obj.last_15min_weight + 
            obj.last_1hour_weight + 
            obj.last_4hour_weight + 
            obj.today_weight
        )
        
        if abs(total_weight - 1.0) > 0.05:
            messages.warning(
                request,
                f"⚠️ Weight distribution sums to {total_weight:.3f}, should be close to 1.0"
            )
        
        if change:
            messages.success(
                request,
                f"✅ Configuration '{obj.name}' has been updated successfully"
            )
        else:
            messages.success(
                request,
                f"🎉 New configuration '{obj.name}' has been created"
            )
    
    def get_queryset(self, request):
        """Order by active status and name"""
        return super().get_queryset(request).order_by('-is_active', 'name')
    
    actions = ['activate_configuration', 'deactivate_configuration', 'duplicate_configuration']
    
    def activate_configuration(self, request, queryset):
        """Activate selected configurations"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"✅ {updated} configurations activated",
            messages.SUCCESS
        )
    activate_configuration.short_description = "Activate selected configurations"
    
    def deactivate_configuration(self, request, queryset):
        """Deactivate selected configurations"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"⏸️ {updated} configurations deactivated",
            messages.SUCCESS
        )
    deactivate_configuration.short_description = "Deactivate selected configurations"
    
    def duplicate_configuration(self, request, queryset):
        """Duplicate selected configurations"""
        duplicated = 0
        for config in queryset:
            config.pk = None
            config.name = f"{config.name}_copy"
            config.is_active = False
            config.save()
            duplicated += 1
            
        self.message_user(
            request,
            f"📋 {duplicated} configurations duplicated",
            messages.SUCCESS
        )
    duplicate_configuration.short_description = "Duplicate selected configurations"
