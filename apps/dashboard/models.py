"""
Dashboard models for GPW Trading Advisor.
User dashboard configuration and widgets.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models import SoftDeleteModel, StockSymbol
from typing import Any, Dict, List, Optional

User = get_user_model()


class DashboardLayout(SoftDeleteModel):
    """
    User's dashboard layout configuration.
    """
    LAYOUT_TYPES = [
        ('grid', 'Grid Layout'),
        ('list', 'List Layout'),
        ('cards', 'Card Layout'),
        ('custom', 'Custom Layout'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_layout'
    )
    name = models.CharField(max_length=200, default='My Dashboard')
    layout_type = models.CharField(max_length=20, choices=LAYOUT_TYPES, default='grid')
    
    # Layout configuration
    columns = models.PositiveIntegerField(default=3)
    theme = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto'),
        ],
        default='light'
    )
    
    # Widget positions and sizes
    layout_config = models.JSONField(
        default=dict,
        help_text="Widget positions and configurations"
    )
    
    # Preferences
    auto_refresh_interval = models.PositiveIntegerField(
        default=300,
        help_text="Auto refresh interval in seconds"
    )
    show_animations = models.BooleanField(default=True)
    compact_mode = models.BooleanField(default=False)
    
    # Last accessed
    last_accessed = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.name}"

    def get_widget_config(self, widget_id: str) -> Dict[str, Any]:
        """Get configuration for a specific widget."""
        return self.layout_config.get('widgets', {}).get(widget_id, {})

    def set_widget_config(self, widget_id: str, config: Dict[str, Any]) -> None:
        """Set configuration for a specific widget."""
        if 'widgets' not in self.layout_config:
            self.layout_config['widgets'] = {}
        
        self.layout_config['widgets'][widget_id] = config
        self.save(update_fields=['layout_config'])

    def add_widget(self, widget_type: str, position: Dict[str, int], config: Optional[Dict[str, Any]] = None) -> str:
        """Add a new widget to the dashboard."""
        import uuid
        widget_id = str(uuid.uuid4())
        
        widget_config = {
            'type': widget_type,
            'position': position,
            'config': config or {},
            'created_at': timezone.now().isoformat(),
        }
        
        self.set_widget_config(widget_id, widget_config)
        return widget_id

    def remove_widget(self, widget_id: str) -> bool:
        """Remove a widget from the dashboard."""
        if 'widgets' in self.layout_config and widget_id in self.layout_config['widgets']:
            del self.layout_config['widgets'][widget_id]
            self.save(update_fields=['layout_config'])
            return True
        return False

    class Meta(SoftDeleteModel.Meta):
        db_table = 'dashboard_layout'
        verbose_name = 'Dashboard Layout'
        verbose_name_plural = 'Dashboard Layouts'


class Widget(SoftDeleteModel):
    """
    Available dashboard widgets.
    """
    WIDGET_TYPES = [
        ('portfolio_summary', 'Portfolio Summary'),
        ('watchlist', 'Stock Watchlist'),
        ('recent_signals', 'Recent Trading Signals'),
        ('market_overview', 'Market Overview'),
        ('performance_chart', 'Performance Chart'),
        ('top_gainers', 'Top Gainers'),
        ('top_losers', 'Top Losers'),
        ('news_feed', 'News Feed'),
        ('economic_calendar', 'Economic Calendar'),
        ('quick_actions', 'Quick Actions'),
        ('notifications', 'Notifications'),
        ('system_status', 'System Status'),
    ]

    SIZE_OPTIONS = [
        ('small', 'Small (1x1)'),
        ('medium', 'Medium (2x1)'),
        ('large', 'Large (2x2)'),
        ('wide', 'Wide (3x1)'),
        ('tall', 'Tall (1x2)'),
        ('extra_large', 'Extra Large (3x2)'),
    ]

    name = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPES, unique=True)
    description = models.TextField(blank=True)
    
    # Widget properties
    default_size = models.CharField(max_length=20, choices=SIZE_OPTIONS, default='medium')
    is_resizable = models.BooleanField(default=True)
    is_moveable = models.BooleanField(default=True)
    requires_data_source = models.BooleanField(default=False)
    
    # Configuration options
    config_schema = models.JSONField(
        default=dict,
        help_text="JSON schema for widget configuration"
    )
    default_config = models.JSONField(
        default=dict,
        help_text="Default configuration values"
    )
    
    # Requirements
    min_subscription_level = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('premium', 'Premium'),
            ('pro', 'Professional'),
        ],
        default='free'
    )
    
    # Status
    is_enabled = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default='1.0.0')

    def __str__(self) -> str:
        return f"{self.name} ({self.widget_type})"

    def can_user_access(self, user) -> bool:
        """Check if user can access this widget based on subscription."""
        if not self.is_enabled:
            return False
        
        # Check subscription level
        if self.min_subscription_level == 'free':
            return True
        elif self.min_subscription_level == 'premium':
            return getattr(user, 'is_premium', False)
        elif self.min_subscription_level == 'pro':
            # Assuming pro is highest level
            return getattr(user, 'is_premium', False)  # Adjust based on actual implementation
        
        return False

    @classmethod
    def get_available_for_user(cls, user) -> List['Widget']:
        """Get all widgets available for a user."""
        return [widget for widget in cls.active.filter(is_enabled=True) 
                if widget.can_user_access(user)]

    class Meta(SoftDeleteModel.Meta):
        db_table = 'dashboard_widget'
        verbose_name = 'Widget'
        verbose_name_plural = 'Widgets'
        ordering = ['name']


class UserWidget(SoftDeleteModel):
    """
    User's configured widgets on their dashboard.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_widgets'
    )
    widget = models.ForeignKey(
        Widget,
        on_delete=models.CASCADE,
        related_name='user_instances'
    )
    
    # Position and size
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=1)
    height = models.PositiveIntegerField(default=1)
    
    # Configuration
    title = models.CharField(max_length=200, blank=True)
    config = models.JSONField(default=dict, help_text="Widget-specific configuration")
    
    # Data source (if applicable)
    data_source = models.CharField(max_length=200, blank=True)
    refresh_interval = models.PositiveIntegerField(
        default=300,
        help_text="Refresh interval in seconds"
    )
    
    # Display options
    is_visible = models.BooleanField(default=True)
    show_header = models.BooleanField(default=True)
    show_border = models.BooleanField(default=True)
    
    # Order
    display_order = models.PositiveIntegerField(default=0)
    
    # Last data update
    last_updated = models.DateTimeField(null=True, blank=True)
    cached_data = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        title = self.title or self.widget.name
        return f"{self.user.username} - {title}"

    @property
    def display_title(self) -> str:
        """Get the title to display for this widget."""
        return self.title or self.widget.name

    @property
    def is_data_stale(self) -> bool:
        """Check if cached data is stale based on refresh interval."""
        if not self.last_updated:
            return True
        
        stale_threshold = timezone.now() - timezone.timedelta(seconds=self.refresh_interval)
        return self.last_updated < stale_threshold

    def update_cached_data(self, data: Dict[str, Any]) -> None:
        """Update cached data for the widget."""
        self.cached_data = data
        self.last_updated = timezone.now()
        self.save(update_fields=['cached_data', 'last_updated'])

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, self.widget.default_config.get(key, default))

    def set_config_value(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.config[key] = value
        self.save(update_fields=['config'])

    def move_to(self, x: int, y: int) -> None:
        """Move widget to new position."""
        self.position_x = x
        self.position_y = y
        self.save(update_fields=['position_x', 'position_y'])

    def resize_to(self, width: int, height: int) -> None:
        """Resize widget."""
        if self.widget.is_resizable:
            self.width = width
            self.height = height
            self.save(update_fields=['width', 'height'])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'dashboard_user_widget'
        verbose_name = 'User Widget'
        verbose_name_plural = 'User Widgets'
        unique_together = ['user', 'widget', 'position_x', 'position_y']
        ordering = ['display_order', 'position_y', 'position_x']


class DashboardAlert(SoftDeleteModel):
    """
    Alerts and notifications displayed on the dashboard.
    """
    ALERT_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('success', 'Success'),
        ('market', 'Market Alert'),
        ('system', 'System Alert'),
    ]

    ALERT_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_alerts',
        null=True,
        blank=True,
        help_text="Specific user (if null, alert is global)"
    )
    
    # Alert content
    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    level = models.CharField(max_length=20, choices=ALERT_LEVELS, default='medium')
    
    # Display options
    is_dismissible = models.BooleanField(default=True)
    auto_dismiss_after = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Auto dismiss after X seconds"
    )
    show_on_dashboard = models.BooleanField(default=True)
    show_as_notification = models.BooleanField(default=False)
    
    # Timing
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    # Related objects
    related_stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dashboard_alerts'
    )
    
    # Metadata
    source = models.CharField(max_length=100, default='system')
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.alert_type})"

    @property
    def is_active(self) -> bool:
        """Check if alert is currently active."""
        now = timezone.now()
        
        if self.is_dismissed:
            return False
        
        if now < self.valid_from:
            return False
        
        if self.valid_until and now > self.valid_until:
            return False
        
        return True

    @property
    def is_expired(self) -> bool:
        """Check if alert has expired."""
        if not self.valid_until:
            return False
        return timezone.now() > self.valid_until

    def mark_as_read(self) -> None:
        """Mark alert as read."""
        self.is_read = True
        self.save(update_fields=['is_read'])

    def dismiss(self) -> None:
        """Dismiss the alert."""
        self.is_dismissed = True
        self.dismissed_at = timezone.now()
        self.save(update_fields=['is_dismissed', 'dismissed_at'])

    @classmethod
    def get_active_for_user(cls, user) -> List['DashboardAlert']:
        """Get all active alerts for a user."""
        now = timezone.now()
        return list(cls.active.filter(
            models.Q(user=user) | models.Q(user__isnull=True),
            is_dismissed=False,
            valid_from__lte=now,
            show_on_dashboard=True
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=now)
        ).order_by('-level', '-created_at'))

    @classmethod
    def create_system_alert(cls, title: str, message: str, alert_type: str = 'info', 
                          level: str = 'medium', user=None) -> 'DashboardAlert':
        """Create a system alert."""
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            alert_type=alert_type,
            level=level,
            source='system'
        )

    class Meta(SoftDeleteModel.Meta):
        db_table = 'dashboard_alert'
        verbose_name = 'Dashboard Alert'
        verbose_name_plural = 'Dashboard Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_dismissed', 'valid_from']),
            models.Index(fields=['alert_type', 'level']),
        ]
