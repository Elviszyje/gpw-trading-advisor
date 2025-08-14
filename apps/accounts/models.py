"""
Custom User Model for GPW2 Trading Intelligence Platform
Extends Django's AbstractUser with trading-specific fields
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel


class User(AbstractUser):
    """
    Custom user model with trading-specific functionality
    """
    # Basic profile information
    full_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=100, blank=True)
    
    # Trading preferences
    preferred_stocks = models.ManyToManyField(
        'core.StockSymbol',
        blank=True,
        related_name='subscribers',
        help_text="Stocks this user wants to monitor"
    )
    
    preferred_industries = models.ManyToManyField(
        'core.Industry',
        blank=True,
        related_name='subscribers',
        help_text="Industries this user is interested in"
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications"
    )
    
    sms_notifications = models.BooleanField(
        default=False,
        help_text="Receive SMS notifications"
    )
    
    sentiment_alert_threshold = models.FloatField(
        default=0.8,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)],
        help_text="Sentiment threshold for alerts (0.1-1.0)"
    )
    
    impact_alert_threshold = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)],
        help_text="Impact threshold for alerts (0.1-1.0)"
    )
    
    # Dashboard preferences
    dashboard_refresh_interval = models.IntegerField(
        default=300,  # 5 minutes
        validators=[MinValueValidator(60), MaxValueValidator(3600)],
        help_text="Dashboard auto-refresh interval in seconds (60-3600)"
    )
    
    default_analysis_period = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Default period for analytics in days (1-365)"
    )
    
    timezone_preference = models.CharField(
        max_length=50,
        default='Europe/Warsaw',
        help_text="User's preferred timezone"
    )
    
    # Access control
    can_access_analytics = models.BooleanField(
        default=True,
        help_text="Can access analytics dashboard"
    )
    
    can_export_data = models.BooleanField(
        default=False,
        help_text="Can export analytics data"
    )
    
    can_manage_alerts = models.BooleanField(
        default=True,
        help_text="Can create and manage custom alerts"
    )
    
    api_access_enabled = models.BooleanField(
        default=False,
        help_text="Can access REST API endpoints"
    )
    
    # Usage tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.IntegerField(default=0)
    last_dashboard_access = models.DateTimeField(null=True, blank=True)
    
    # Profile completion
    profile_completed = models.BooleanField(
        default=False,
        help_text="Has user completed their profile setup"
    )
    
    onboarding_completed = models.BooleanField(
        default=False,
        help_text="Has user completed onboarding process"
    )
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.get_display_name()
    
    def get_display_name(self):
        """Get user's display name"""
        if self.full_name:
            return self.full_name
        return self.username
    
    def get_full_name(self):
        """Override AbstractUser's get_full_name"""
        return self.full_name or f"{self.first_name} {self.last_name}".strip() or self.username
    
    def increment_login_count(self, ip_address=None):
        """Track user login"""
        self.login_count += 1
        if ip_address:
            self.last_login_ip = ip_address
        self.save(update_fields=['login_count', 'last_login_ip'])
    
    def update_dashboard_access(self):
        """Track dashboard access"""
        self.last_dashboard_access = timezone.now()
        self.save(update_fields=['last_dashboard_access'])
    
    def get_alert_settings(self):
        """Get user's alert configuration"""
        return {
            'sentiment_threshold': self.sentiment_alert_threshold,
            'impact_threshold': self.impact_alert_threshold,
            'email_notifications': self.email_notifications,
            'sms_notifications': self.sms_notifications,
            'preferred_stocks': list(self.preferred_stocks.values_list('symbol', flat=True)),
            'preferred_industries': list(self.preferred_industries.values_list('name', flat=True))
        }


class UserProfile(TimeStampedModel):
    """
    Extended user profile with additional metadata
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Professional information
    license_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Professional trading license number"
    )
    
    experience_years = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Years of trading experience"
    )
    
    investment_focus = models.CharField(
        max_length=20,
        choices=[
            ('growth', 'Growth Stocks'),
            ('value', 'Value Investing'),
            ('dividend', 'Dividend Stocks'),
            ('day_trading', 'Day Trading'),
            ('swing', 'Swing Trading'),
            ('long_term', 'Long-term Investing'),
            ('mixed', 'Mixed Strategy'),
        ],
        blank=True,
        help_text="Primary investment strategy"
    )
    
    risk_tolerance = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('aggressive', 'Aggressive'),
        ],
        default='medium',
        help_text="Risk tolerance level"
    )
    
    # Portfolio information
    portfolio_size_range = models.CharField(
        max_length=20,
        choices=[
            ('0-10k', '0 - 10k PLN'),
            ('10k-50k', '10k - 50k PLN'),
            ('50k-100k', '50k - 100k PLN'),
            ('100k-500k', '100k - 500k PLN'),
            ('500k-1m', '500k - 1M PLN'),
            ('1m+', '1M+ PLN'),
        ],
        blank=True,
        help_text="Portfolio size range"
    )
    
    # Analytics preferences
    favorite_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="User's favorite analytics metrics"
    )
    
    custom_watchlists = models.JSONField(
        default=list,
        blank=True,
        help_text="Custom stock watchlists"
    )
    
    dashboard_layout = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom dashboard layout preferences"
    )
    
    # Settings
    dark_mode = models.BooleanField(
        default=False,
        help_text="Prefer dark mode interface"
    )
    
    compact_view = models.BooleanField(
        default=False,
        help_text="Use compact dashboard layout"
    )
    
    show_tutorials = models.BooleanField(
        default=True,
        help_text="Show tutorial hints and tips"
    )
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.get_display_name()}"


class UserSession(TimeStampedModel):
    """
    Track user sessions for analytics and security
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Session metadata
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    
    # Activity tracking
    pages_visited = models.IntegerField(default=0)
    api_calls_made = models.IntegerField(default=0)
    exports_performed = models.IntegerField(default=0)
    
    # Session data
    session_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional session metadata"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_sessions'
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
        ]
    
    def __str__(self):
        return f"Session for {self.user.username} at {self.login_time}"
    
    def duration(self):
        """Get session duration"""
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time
    
    def mark_logout(self):
        """Mark session as logged out"""
        self.logout_time = timezone.now()
        self.is_active = False
        self.save(update_fields=['logout_time', 'is_active'])


class UserAlert(TimeStampedModel):
    """
    Custom user alerts and notifications
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    
    # Alert configuration
    name = models.CharField(
        max_length=100,
        help_text="Alert name/description"
    )
    
    alert_type = models.CharField(
        max_length=20,
        choices=[
            ('sentiment', 'Sentiment Alert'),
            ('stock_mention', 'Stock Mention Alert'),
            ('industry_news', 'Industry News Alert'),
            ('market_impact', 'Market Impact Alert'),
            ('custom', 'Custom Alert'),
        ],
        help_text="Type of alert"
    )
    
    # Target criteria
    target_stocks = models.ManyToManyField(
        'core.StockSymbol',
        blank=True,
        help_text="Stocks to monitor for this alert"
    )
    
    target_industries = models.ManyToManyField(
        'core.Industry',
        blank=True,
        help_text="Industries to monitor for this alert"
    )
    
    # Threshold settings
    sentiment_threshold = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Sentiment threshold (-1.0 to 1.0)"
    )
    
    impact_threshold = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Impact threshold (0.0 to 1.0)"
    )
    
    # Delivery settings
    delivery_methods = models.JSONField(
        default=list,
        help_text="How to deliver this alert (email, sms, dashboard)"
    )
    
    frequency_limit = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Maximum once per hour'),
            ('daily', 'Maximum once per day'),
            ('weekly', 'Maximum once per week'),
        ],
        default='immediate',
        help_text="Alert frequency limitation"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Is this alert active"
    )
    
    last_triggered = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this alert was last triggered"
    )
    
    trigger_count = models.IntegerField(
        default=0,
        help_text="How many times this alert has been triggered"
    )
    
    class Meta:
        db_table = 'user_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['alert_type']),
        ]
    
    def __str__(self):
        return f"Alert '{self.name}' for {self.user.username}"
    
    def can_trigger(self):
        """Check if alert can be triggered based on frequency limit"""
        if not self.is_active:
            return False
        
        if not self.last_triggered:
            return True
        
        now = timezone.now()
        time_since_last = now - self.last_triggered
        
        frequency_map = {
            'immediate': timezone.timedelta(0),
            'hourly': timezone.timedelta(hours=1),
            'daily': timezone.timedelta(days=1),
            'weekly': timezone.timedelta(weeks=1),
        }
        
        min_interval = frequency_map.get(self.frequency_limit, timezone.timedelta(0))
        return time_since_last >= min_interval
    
    def trigger(self):
        """Mark alert as triggered"""
        self.last_triggered = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=['last_triggered', 'trigger_count'])


class UserNotification(TimeStampedModel):
    """
    Delivered notifications/alerts to users
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Notification details
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    notification_type = models.CharField(
        max_length=20,
        choices=[
            ('sentiment', 'Sentiment Alert'),
            ('stock_mention', 'Stock Mention'),
            ('industry_news', 'Industry News'),
            ('market_impact', 'Market Impact'),
            ('system', 'System Notification'),
            ('custom', 'Custom Alert'),
        ],
        default='system'
    )
    
    # Related data
    related_stocks = models.ManyToManyField(
        'core.StockSymbol',
        blank=True,
        help_text="Stocks related to this notification"
    )
    
    related_alert = models.ForeignKey(
        UserAlert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Alert that triggered this notification"
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Priority
    priority = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        default='medium'
    )
    
    # Additional data
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional notification data"
    )
    
    class Meta:
        db_table = 'user_notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
