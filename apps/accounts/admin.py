"""
Custom Django admin configuration for user management
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User, UserProfile, UserSession, UserAlert, UserNotification


class UserProfileInline(admin.StackedInline):
    """Inline for UserProfile in User admin"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    
    fieldsets = (
        ('Professional Information', {
            'fields': ('license_number', 'experience_years', 'investment_focus', 'risk_tolerance')
        }),
        ('Portfolio Information', {
            'fields': ('portfolio_size_range', 'favorite_metrics', 'custom_watchlists')
        }),
        ('Interface Preferences', {
            'fields': ('dashboard_layout', 'dark_mode', 'compact_view', 'show_tutorials')
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced User admin with trading-specific features"""
    
    inlines = (UserProfileInline,)
    
    # List display
    list_display = (
        'username',
        'email',
        'full_name',
        'company',
        'is_active',
        'profile_status',
        'last_login_display',
        'login_count',
        'alert_count',
        'permissions_summary'
    )
    
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'profile_completed',
        'onboarding_completed',
        'can_access_analytics',
        'can_export_data',
        'email_notifications',
        'date_joined',
        'last_login',
    )
    
    search_fields = (
        'username',
        'email',
        'full_name',
        'first_name',
        'last_name',
        'company',
    )
    
    ordering = ('-date_joined',)
    
    # Fieldsets for add/change forms
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'full_name', 'email', 'phone_number')
        }),
        ('Professional Info', {
            'fields': ('company', 'position')
        }),
        ('Trading Preferences', {
            'fields': ('preferred_stocks', 'preferred_industries')
        }),
        ('Notification Settings', {
            'fields': (
                'email_notifications',
                'sms_notifications',
                'sentiment_alert_threshold',
                'impact_alert_threshold'
            )
        }),
        ('Dashboard Preferences', {
            'fields': (
                'dashboard_refresh_interval',
                'default_analysis_period',
                'timezone_preference'
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
                'can_access_analytics',
                'can_export_data',
                'can_manage_alerts',
                'api_access_enabled'
            )
        }),
        ('Status', {
            'fields': (
                'profile_completed',
                'onboarding_completed',
                'last_login',
                'date_joined'
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
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        ('Profile', {
            'classes': ('wide',),
            'fields': ('full_name', 'company', 'phone_number'),
        }),
        ('Permissions', {
            'classes': ('wide',),
            'fields': ('can_access_analytics', 'can_export_data', 'can_manage_alerts'),
        }),
    )
    
    filter_horizontal = ('groups', 'user_permissions', 'preferred_stocks', 'preferred_industries')
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related(
            'profile'
        ).prefetch_related(
            'alerts',
            'sessions',
            'preferred_stocks',
            'preferred_industries'
        ).annotate(
            alert_count=Count('alerts'),
            session_count=Count('sessions')
        )
    
    def profile_status(self, obj):
        """Display profile completion status"""
        if obj.profile_completed and obj.onboarding_completed:
            return format_html(
                '<span style="color: green;">✓ Complete</span>'
            )
        elif obj.profile_completed:
            return format_html(
                '<span style="color: orange;">⚠ Onboarding pending</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Incomplete</span>'
            )
    profile_status.short_description = 'Profile Status'
    
    def last_login_display(self, obj):
        """Enhanced last login display"""
        if obj.last_login:
            now = timezone.now()
            diff = now - obj.last_login
            
            if diff.days > 30:
                color = 'red'
                status = f'{diff.days} days ago'
            elif diff.days > 7:
                color = 'orange'
                status = f'{diff.days} days ago'
            elif diff.days > 0:
                color = 'blue'
                status = f'{diff.days} days ago'
            else:
                color = 'green'
                hours = diff.seconds // 3600
                if hours > 0:
                    status = f'{hours}h ago'
                else:
                    minutes = diff.seconds // 60
                    status = f'{minutes}m ago'
            
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                status
            )
        return format_html('<span style="color: gray;">Never</span>')
    last_login_display.short_description = 'Last Login'
    
    def alert_count(self, obj):
        """Display number of active alerts"""
        return obj.alert_count
    alert_count.short_description = 'Alerts'
    alert_count.admin_order_field = 'alert_count'
    
    def permissions_summary(self, obj):
        """Summary of user permissions"""
        perms = []
        if obj.can_access_analytics:
            perms.append('📊')
        if obj.can_export_data:
            perms.append('💾')
        if obj.can_manage_alerts:
            perms.append('🚨')
        if obj.api_access_enabled:
            perms.append('🔗')
        if obj.is_superuser:
            perms.append('👑')
        elif obj.is_staff:
            perms.append('🔧')
        
        return ' '.join(perms) if perms else '👤'
    permissions_summary.short_description = 'Permissions'
    
    # Custom actions
    actions = ['activate_users', 'deactivate_users', 'complete_onboarding', 'enable_analytics_access']
    
    def activate_users(self, request, queryset):
        """Activate selected users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} users.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} users.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def complete_onboarding(self, request, queryset):
        """Mark onboarding as completed"""
        updated = queryset.update(onboarding_completed=True)
        self.message_user(request, f'Completed onboarding for {updated} users.')
    complete_onboarding.short_description = 'Complete onboarding'
    
    def enable_analytics_access(self, request, queryset):
        """Enable analytics access for selected users"""
        updated = queryset.update(can_access_analytics=True)
        self.message_user(request, f'Enabled analytics access for {updated} users.')
    enable_analytics_access.short_description = 'Enable analytics access'


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin for user sessions"""
    
    list_display = (
        'user',
        'login_time',
        'last_activity',
        'duration_display',
        'ip_address',
        'is_active',
        'activity_summary'
    )
    
    list_filter = (
        'is_active',
        'login_time',
        'last_activity',
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'ip_address',
        'session_key'
    )
    
    readonly_fields = (
        'session_key',
        'login_time',
        'duration_display',
        'user_agent'
    )
    
    ordering = ('-login_time',)
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user')
    
    def duration_display(self, obj):
        """Display session duration"""
        duration = obj.duration()
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        
        if hours > 0:
            return f'{int(hours)}h {int(minutes)}m'
        else:
            return f'{int(minutes)}m'
    duration_display.short_description = 'Duration'
    
    def activity_summary(self, obj):
        """Display activity summary"""
        return f'📄 {obj.pages_visited} | 🔗 {obj.api_calls_made} | 💾 {obj.exports_performed}'
    activity_summary.short_description = 'Activity'


@admin.register(UserAlert)
class UserAlertAdmin(admin.ModelAdmin):
    """Admin for user alerts"""
    
    list_display = (
        'name',
        'user',
        'alert_type',
        'is_active',
        'trigger_count',
        'last_triggered',
        'frequency_limit'
    )
    
    list_filter = (
        'alert_type',
        'is_active',
        'frequency_limit',
        'created_at',
        'last_triggered'
    )
    
    search_fields = (
        'name',
        'user__username',
        'user__email'
    )
    
    readonly_fields = (
        'trigger_count',
        'last_triggered',
        'created_at',
        'updated_at'
    )
    
    filter_horizontal = ('target_stocks', 'target_industries')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'alert_type', 'is_active')
        }),
        ('Targets', {
            'fields': ('target_stocks', 'target_industries')
        }),
        ('Thresholds', {
            'fields': ('sentiment_threshold', 'impact_threshold')
        }),
        ('Delivery', {
            'fields': ('delivery_methods', 'frequency_limit')
        }),
        ('Statistics', {
            'fields': ('trigger_count', 'last_triggered', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user')


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    """Admin interface for user notifications"""
    
    list_display = [
        'title',
        'user',
        'notification_type',
        'priority',
        'is_read',
        'created_at',
        'read_status'
    ]
    
    list_filter = [
        'notification_type',
        'priority',
        'is_read',
        'created_at',
    ]
    
    search_fields = [
        'title',
        'message',
        'user__username',
        'user__email',
        'user__full_name',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'read_at',
    ]
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('title', 'message', 'notification_type', 'priority')
        }),
        ('User & Targeting', {
            'fields': ('user', 'related_stocks', 'related_alert')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'data')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['related_stocks']
    
    def read_status(self, obj):
        """Display read status with icon"""
        if obj.is_read:
            return format_html(
                '<span style="color: green;">✓ Read</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Unread</span>'
            )
    read_status.short_description = 'Status'  # type: ignore
    
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


# Customize admin site
admin.site.site_header = 'GPW2 Trading Intelligence - Administration'
admin.site.site_title = 'GPW2 Admin'
admin.site.index_title = 'Trading Platform Administration'
