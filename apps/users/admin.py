from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SubscriptionPlan, Subscription, NotificationPreferences, UserStockWatchlist


"""
Admin configuration for user management
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone

from .models import User, UserProfile, UserSession, UserNotification, SubscriptionPlan, Subscription, NotificationPreferences, UserStockWatchlist


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced user admin with trading-specific fields"""
    
    list_display = [
        'username',
        'email',
        'full_name',
        'is_verified',
        'profile_status',
        'onboarding_status',
        'last_login',
        'date_joined'
    ]
    
    list_filter = [
        'is_verified',
        'profile_completed',
        'onboarding_completed',
        'can_access_analytics',
        'api_access_enabled',
        'date_joined',
        'last_login'
    ]
    
    search_fields = [
        'username',
        'email',
        'full_name',
        'company'
    ]
    
    readonly_fields = [
        'date_joined',
        'last_login',
        'login_count',
        'last_login_ip',
        'last_dashboard_access'
    ]
    
    fieldsets = BaseUserAdmin.fieldsets + (  # type: ignore
        ('Profile Information', {
            'fields': (
                'full_name',
                'company',
                'position',
                'phone_number',
                'telegram_chat_id'
            )
        }),
        ('Notification Preferences', {
            'fields': (
                'email_notifications',
                'sms_notifications',
                'sentiment_alert_threshold',
                'impact_alert_threshold'
            )
        }),
        ('Dashboard Settings', {
            'fields': (
                'dashboard_refresh_interval',
                'default_analysis_period',
                'timezone_preference'
            )
        }),
        ('Permissions & Access', {
            'fields': (
                'can_access_analytics',
                'can_export_data',
                'can_manage_alerts',
                'api_access_enabled'
            )
        }),
        ('Status', {
            'fields': (
                'is_verified',
                'profile_completed',
                'onboarding_completed'
            )
        }),
        ('Usage Tracking', {
            'fields': (
                'login_count',
                'last_login_ip',
                'last_dashboard_access'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def profile_status(self, obj):
        """Display profile completion status"""
        if obj.profile_completed:
            return format_html('<span style="color: green;">✓ Complete</span>')
        else:
            return format_html('<span style="color: red;">✗ Incomplete</span>')
    profile_status.short_description = 'Profile'  # type: ignore
    
    def onboarding_status(self, obj):
        """Display onboarding status"""
        if obj.onboarding_completed:
            return format_html('<span style="color: green;">✓ Done</span>')
        else:
            return format_html('<span style="color: orange;">Pending</span>')
    onboarding_status.short_description = 'Onboarding'  # type: ignore


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin for user profiles"""
    
    list_display = [
        'user',
        'experience_years',
        'investment_focus',
        'risk_tolerance',
        'portfolio_size_range',
        'created_at'
    ]
    
    list_filter = [
        'investment_focus',
        'risk_tolerance',
        'portfolio_size_range',
        'dark_mode',
        'compact_view'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'user__full_name',
        'license_number'
    ]
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin for user sessions"""
    
    list_display = [
        'user',
        'ip_address',
        'login_time',
        'last_activity',
        'is_active',
        'pages_visited'
    ]
    
    list_filter = [
        'is_active',
        'login_time',
        'last_activity'
    ]
    
    search_fields = [
        'user__username',
        'ip_address',
        'user_agent'
    ]
    
    readonly_fields = [
        'login_time',
        'created_at',
        'updated_at'
    ]
    
    date_hierarchy = 'login_time'
    ordering = ['-login_time']


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    """Admin for user notifications"""
    
    list_display = [
        'title',
        'user',
        'notification_type',
        'priority',
        'is_read',
        'created_at'
    ]
    
    list_filter = [
        'notification_type',
        'priority',
        'is_read',
        'created_at'
    ]
    
    search_fields = [
        'title',
        'message',
        'user__username',
        'user__email'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'read_at'
    ]
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read"""
        updated = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        self.message_user(request, f'{updated} notifications marked as read.')
    mark_as_read.short_description = "Mark selected notifications as read"  # type: ignore
    
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread"""
        updated = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None
        )
        self.message_user(request, f'{updated} notifications marked as unread.')
    mark_as_unread.short_description = "Mark selected notifications as unread"  # type: ignore


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan_type', 'price', 'duration_days', 'max_stocks_monitored', 'is_active']
    list_filter = ['plan_type', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['price']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'start_date', 'end_date', 'is_active', 'payment_status']
    list_filter = ['plan', 'payment_status', 'is_active']
    search_fields = ['user__username', 'user__email']
    ordering = ['-start_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(NotificationPreferences)
class NotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'telegram_enabled', 'email_enabled', 'stock_alerts', 'daily_summary']
    list_filter = ['telegram_enabled', 'email_enabled', 'stock_alerts', 'daily_summary']
    search_fields = ['user__username']


@admin.register(UserStockWatchlist)
class UserStockWatchlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'stock', 'added_at', 'is_active']
    list_filter = ['is_active', 'added_at']
    search_fields = ['user__username', 'stock__symbol']
    ordering = ['-added_at']
