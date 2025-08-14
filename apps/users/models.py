"""
User models for GPW Trading Advisor.
Subscription and notification preferences management.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from apps.core.models import SoftDeleteModel, StockSymbol, TimeStampedModel
from typing import Any, Dict, List, Optional


class User(AbstractUser):
    """
    Extended user model for GPW Trading Advisor.
    """
    # Basic profile info
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    full_name = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=100, blank=True)
    
    # Account status
    is_verified = models.BooleanField(default=False)
    
    # Communication preferences
    telegram_chat_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text="Telegram chat ID for notifications"
    )
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications"
    )
    sms_notifications = models.BooleanField(
        default=False,
        help_text="Receive SMS notifications"
    )
    
    # Alert thresholds
    sentiment_alert_threshold = models.FloatField(
        default=0.8,
        help_text="Sentiment threshold for alerts (0.1-1.0)"
    )
    impact_alert_threshold = models.FloatField(
        default=0.7,
        help_text="Impact threshold for alerts (0.1-1.0)"
    )
    
    # Dashboard preferences
    dashboard_refresh_interval = models.IntegerField(
        default=300,  # 5 minutes
        help_text="Dashboard auto-refresh interval in seconds"
    )
    default_analysis_period = models.IntegerField(
        default=7,
        help_text="Default period for analytics in days"
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.username} ({self.email})"
    
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

    @property
    def has_telegram(self) -> bool:
        """Check if user has Telegram configured."""
        return bool(self.telegram_chat_id)

    @property
    def is_premium(self) -> bool:
        """Check if user has active premium subscription."""
        try:
            from apps.users.models import Subscription
            return Subscription.objects.filter(
                user=self,
                is_active=True,
                subscription_type='premium',
                end_date__gt=timezone.now()
            ).exists()
        except ImportError:
            return False

    class Meta:
        db_table = 'users_user'


class UserProfile(TimeStampedModel):
    """
    Extended user profile with trading-specific information
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Trading information
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
        help_text="Primary investment focus"
    )
    
    risk_tolerance = models.CharField(
        max_length=15,
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('aggressive', 'Aggressive'),
        ],
        blank=True,
        help_text="Risk tolerance level"
    )
    
    portfolio_size_range = models.CharField(
        max_length=20,
        choices=[
            ('small', 'Up to 10K PLN'),
            ('medium', '10K - 100K PLN'),
            ('large', '100K - 1M PLN'),
            ('institutional', 'Over 1M PLN'),
        ],
        blank=True,
        help_text="Approximate portfolio size"
    )
    
    # Personal information
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Date of birth"
    )
    
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country of residence"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City of residence"
    )
    
    # Trading information
    trading_experience = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner (0-1 years)'),
            ('intermediate', 'Intermediate (1-5 years)'),
            ('advanced', 'Advanced (5+ years)'),
            ('professional', 'Professional'),
        ],
        blank=True,
        help_text="Trading experience level"
    )
    
    investment_goals = models.CharField(
        max_length=20,
        choices=[
            ('retirement', 'Retirement Planning'),
            ('income', 'Income Generation'),
            ('growth', 'Capital Growth'),
            ('speculation', 'Speculation'),
            ('hedging', 'Risk Hedging'),
        ],
        blank=True,
        help_text="Primary investment goals"
    )
    
    preferred_markets = models.CharField(
        max_length=50,
        choices=[
            ('stocks', 'Stocks Only'),
            ('bonds', 'Bonds Only'),
            ('mixed', 'Stocks & Bonds'),
            ('crypto', 'Cryptocurrency'),
            ('commodities', 'Commodities'),
            ('all', 'All Markets'),
        ],
        blank=True,
        help_text="Preferred investment markets"
    )
    
    # Dashboard preferences
    dark_mode = models.BooleanField(
        default=False,
        help_text="Use dark theme"
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
    
    session_key = models.CharField(max_length=40, blank=True)
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
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"Session for {self.user.username} from {self.ip_address}"
    
    def end_session(self):
        """End this session"""
        self.logout_time = timezone.now()
        self.is_active = False
        self.save(update_fields=['logout_time', 'is_active'])


class UserNotification(TimeStampedModel):
    """
    Delivered notifications/alerts to users
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_notifications'
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


class SubscriptionPlan(SoftDeleteModel):
    """
    Available subscription plans.
    """
    PLAN_TYPES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('pro', 'Professional'),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='PLN')
    duration_days = models.PositiveIntegerField(help_text="Subscription duration in days")
    max_stocks_monitored = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of stocks that can be monitored"
    )
    notifications_enabled = models.BooleanField(default=True)
    telegram_notifications = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    advanced_analysis = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.plan_type})"

    @classmethod
    def get_free_plan(cls) -> 'SubscriptionPlan':
        """Get the free plan."""
        return cls.active.get(plan_type='free')

    class Meta(SoftDeleteModel.Meta):
        db_table = 'users_subscription_plan'
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['price']


class Subscription(SoftDeleteModel):
    """
    User subscriptions to plans.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    subscription_type = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.PLAN_TYPES
    )
    auto_renew = models.BooleanField(default=False)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Set subscription type from plan and calculate end date."""
        if not self.subscription_type:
            self.subscription_type = self.plan.plan_type
        
        if not self.end_date:
            self.end_date = self.start_date + timezone.timedelta(
                days=self.plan.duration_days
            )
        
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.plan.name}"

    @property
    def is_expired(self) -> bool:
        """Check if subscription is expired."""
        return timezone.now() > self.end_date

    @property
    def days_remaining(self) -> int:
        """Get number of days remaining in subscription."""
        if self.is_expired:
            return 0
        
        delta = self.end_date - timezone.now()
        return delta.days

    def extend_subscription(self, days: int) -> None:
        """Extend subscription by specified number of days."""
        self.end_date += timezone.timedelta(days=days)
        self.save(update_fields=['end_date', 'updated_at'])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'users_subscription'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-start_date']


class NotificationPreferences(SoftDeleteModel):
    """
    User notification preferences.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # General preferences
    email_enabled = models.BooleanField(default=True)
    telegram_enabled = models.BooleanField(default=False)
    
    # Notification types
    daily_summary = models.BooleanField(default=True)
    stock_alerts = models.BooleanField(default=True)
    price_targets = models.BooleanField(default=True)
    trend_changes = models.BooleanField(default=True)
    volume_alerts = models.BooleanField(default=False)
    
    # Timing preferences
    summary_time = models.TimeField(default=timezone.datetime.strptime('08:00', '%H:%M').time())
    quiet_hours_start = models.TimeField(default=timezone.datetime.strptime('22:00', '%H:%M').time())
    quiet_hours_end = models.TimeField(default=timezone.datetime.strptime('08:00', '%H:%M').time())
    
    # Weekend notifications
    weekend_notifications = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Preferences for {self.user.username}"

    @property
    def can_send_notifications(self) -> bool:
        """Check if notifications can be sent based on preferences."""
        now = timezone.now().time()
        
        # Check quiet hours
        if self.quiet_hours_start <= self.quiet_hours_end:
            # Same day quiet hours
            in_quiet_hours = self.quiet_hours_start <= now <= self.quiet_hours_end
        else:
            # Overnight quiet hours
            in_quiet_hours = now >= self.quiet_hours_start or now <= self.quiet_hours_end
        
        if in_quiet_hours:
            return False
        
        # Check weekend notifications
        if not self.weekend_notifications and timezone.now().weekday() >= 5:
            return False
        
        return True

    class Meta(SoftDeleteModel.Meta):
        db_table = 'users_notification_preferences'
        verbose_name = 'Notification Preferences'
        verbose_name_plural = 'Notification Preferences'


class UserTradingPreferences(SoftDeleteModel):
    """
    User's trading preferences for personalized recommendations.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='trading_preferences'
    )
    
    # Financial Goals & Constraints
    available_capital = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(100)],
        help_text="Available trading capital in PLN"
    )
    
    # Profit Expectations
    target_profit_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('3.0'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('50.0'))],
        help_text="Target profit percentage per trade (0.5% - 50%)"
    )
    
    # Risk Management
    max_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.0'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('20.0'))],
        help_text="Maximum acceptable loss per trade (0.5% - 20%)"
    )
    
    # Time Horizons
    preferred_holding_time_hours = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(48)],
        help_text="Preferred holding time in hours (1-48 hours)"
    )
    
    max_holding_time_hours = models.IntegerField(
        default=8,
        validators=[MinValueValidator(1), MaxValueValidator(168)],  # Max 1 week
        help_text="Maximum holding time in hours (1-168 hours)"
    )
    
    # Confidence Requirements
    min_confidence_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('60.0'),
        validators=[MinValueValidator(Decimal('30.0')), MaxValueValidator(Decimal('95.0'))],
        help_text="Minimum confidence required for signals (30% - 95%)"
    )
    
    # Position Sizing
    max_position_size_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.0'),
        validators=[MinValueValidator(Decimal('1.0')), MaxValueValidator(Decimal('50.0'))],
        help_text="Maximum percentage of capital per position (1% - 50%)"
    )
    
    min_position_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('500.0'),
        validators=[MinValueValidator(Decimal('100.0'))],
        help_text="Minimum position value in PLN"
    )
    
    # Liquidity Requirements
    min_daily_volume = models.BigIntegerField(
        default=10000,
        validators=[MinValueValidator(1000)],
        help_text="Minimum daily volume for stock recommendations"
    )
    
    min_market_cap_millions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.0'),
        validators=[MinValueValidator(Decimal('10.0'))],
        help_text="Minimum market cap in millions PLN"
    )
    
    # Trading Style Preferences
    trading_style = models.CharField(
        max_length=20,
        choices=[
            ('conservative', 'Conservative - Low risk, steady gains'),
            ('moderate', 'Moderate - Balanced risk/reward'),
            ('aggressive', 'Aggressive - Higher risk, higher rewards'),
            ('scalping', 'Scalping - Very short term, small gains'),
            ('swing', 'Swing Trading - Medium term positions'),
        ],
        default='moderate',
        help_text="Preferred trading style"
    )
    
    # Market Conditions
    market_conditions_preference = models.CharField(
        max_length=15,
        choices=[
            ('bull_only', 'Bull Market Only'),
            ('bear_only', 'Bear Market Only'),
            ('all_conditions', 'All Market Conditions'),
            ('trending_only', 'Trending Markets Only'),
            ('range_bound', 'Range-Bound Markets'),
        ],
        default='all_conditions',
        help_text="Preferred market conditions for trading"
    )
    
    # Sector Preferences
    preferred_sectors = models.ManyToManyField(
        'core.StockSymbol',
        blank=True,
        limit_choices_to={'is_active': True},
        help_text="Preferred sectors/stocks for recommendations"
    )
    
    excluded_sectors = models.JSONField(
        default=list,
        blank=True,
        help_text="Sectors to exclude from recommendations"
    )
    
    # Notification Preferences
    notification_frequency = models.CharField(
        max_length=15,
        choices=[
            ('immediate', 'Immediate - All signals'),
            ('hourly', 'Hourly - Batched signals'),
            ('daily', 'Daily - Summary only'),
            ('weekly', 'Weekly - Summary only'),
        ],
        default='immediate',
        help_text="How often to receive trading notifications"
    )
    
    max_signals_per_day = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Maximum number of signals per day"
    )
    
    # Advanced Settings
    use_technical_analysis = models.BooleanField(
        default=True,
        help_text="Include technical analysis in recommendations"
    )
    
    use_fundamental_analysis = models.BooleanField(
        default=False,
        help_text="Include fundamental analysis in recommendations"
    )
    
    use_sentiment_analysis = models.BooleanField(
        default=True,
        help_text="Include market sentiment in recommendations"
    )
    
    # Risk Tolerance Settings
    allow_penny_stocks = models.BooleanField(
        default=False,
        help_text="Allow recommendations for penny stocks (< 1 PLN)"
    )
    
    allow_new_listings = models.BooleanField(
        default=False,
        help_text="Allow recommendations for newly listed stocks"
    )
    
    require_stop_loss = models.BooleanField(
        default=True,
        help_text="Require stop-loss levels in all recommendations"
    )
    
    # Performance Tracking
    track_performance = models.BooleanField(
        default=True,
        help_text="Track and analyze recommendation performance"
    )
    
    auto_adjust_preferences = models.BooleanField(
        default=False,
        help_text="Automatically adjust preferences based on performance"
    )
    
    def __str__(self) -> str:
        return f"Trading preferences for {self.user.username}"
    
    def get_effective_stop_loss_pct(self) -> float:
        """Get effective stop loss percentage based on trading style."""
        style_modifiers = {
            'conservative': 0.8,  # More conservative stop loss
            'moderate': 1.0,      # Use set percentage
            'aggressive': 1.2,    # Allow bigger losses for bigger gains
            'scalping': 0.5,      # Very tight stop loss
            'swing': 1.5,         # Wider stop loss for swings
        }
        
        modifier = style_modifiers.get(self.trading_style, 1.0)
        return float(self.max_loss_percentage) * modifier
    
    def get_effective_take_profit_pct(self) -> float:
        """Get effective take profit percentage based on trading style."""
        style_modifiers = {
            'conservative': 0.8,  # Smaller targets, more certain
            'moderate': 1.0,      # Use set percentage
            'aggressive': 1.5,    # Higher targets for higher risk
            'scalping': 0.4,      # Very small targets, quick profits
            'swing': 2.0,         # Larger targets for longer holds
        }
        
        modifier = style_modifiers.get(self.trading_style, 1.0)
        return float(self.target_profit_percentage) * modifier
    
    def get_position_size_for_signal(self, signal_confidence: float) -> float:
        """Calculate position size based on signal confidence and preferences."""
        if not self.available_capital:
            return 0.0
        
        # Base position size as percentage of capital
        base_size_pct = float(self.max_position_size_percentage)
        
        # Adjust based on confidence (higher confidence = larger position)
        confidence_factor = signal_confidence / 100.0
        
        # Apply trading style modifier
        style_modifiers = {
            'conservative': 0.5,
            'moderate': 1.0,
            'aggressive': 1.5,
            'scalping': 0.3,  # Smaller positions, more trades
            'swing': 1.2,
        }
        
        style_modifier = style_modifiers.get(self.trading_style, 1.0)
        
        # Calculate final position size
        position_size_pct = base_size_pct * confidence_factor * style_modifier
        position_value = float(self.available_capital) * (position_size_pct / 100.0)
        
        # Ensure minimum position value
        return max(position_value, float(self.min_position_value))
    
    def should_recommend_stock(self, stock_data: Dict[str, Any]) -> bool:
        """Check if stock meets user's criteria for recommendations."""
        # Check market cap
        market_cap = stock_data.get('market_cap_millions', 0)
        if market_cap < float(self.min_market_cap_millions):
            return False
        
        # Check daily volume
        daily_volume = stock_data.get('avg_daily_volume', 0)
        if daily_volume < self.min_daily_volume:
            return False
        
        # Check penny stocks preference
        price = stock_data.get('current_price', 0)
        if not self.allow_penny_stocks and price < 1.0:
            return False
        
        # Check sector exclusions
        sector = stock_data.get('sector', '')
        if sector in self.excluded_sectors:
            return False
        
        return True
    
    @classmethod
    def get_default_preferences(cls, user: User) -> 'UserTradingPreferences':
        """Get or create default trading preferences for user."""
        preferences, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'target_profit_percentage': Decimal('3.0'),
                'max_loss_percentage': Decimal('2.0'),
                'min_confidence_threshold': Decimal('60.0'),
                'max_position_size_percentage': Decimal('10.0'),
                'trading_style': 'moderate',
            }
        )
        return preferences
    
    class Meta(SoftDeleteModel.Meta):
        db_table = 'users_trading_preferences'
        verbose_name = 'Trading Preferences'
        verbose_name_plural = 'Trading Preferences'


class UserStockWatchlist(SoftDeleteModel):
    """
    User's stock watchlist for monitoring.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='watchlist'
    )
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='watchers'
    )
    
    # Alert settings
    price_target_upper = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Alert when price goes above this value"
    )
    price_target_lower = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Alert when price goes below this value"
    )
    volume_threshold = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Alert when volume exceeds this threshold"
    )
    
    # Tracking preferences
    track_technical_indicators = models.BooleanField(default=True)
    track_volume_changes = models.BooleanField(default=False)
    track_news_sentiment = models.BooleanField(default=False)
    
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} watching {self.stock.symbol}"

    @property
    def has_price_alerts(self) -> bool:
        """Check if price alerts are configured."""
        return bool(self.price_target_upper or self.price_target_lower)

    def check_price_alerts(self, current_price: float) -> List[str]:
        """Check if any price alerts should be triggered."""
        alerts = []
        
        if self.price_target_upper and current_price >= float(self.price_target_upper):
            alerts.append(f"Price target reached: {current_price} >= {self.price_target_upper}")
        
        if self.price_target_lower and current_price <= float(self.price_target_lower):
            alerts.append(f"Price alert: {current_price} <= {self.price_target_lower}")
        
        return alerts

    class Meta(SoftDeleteModel.Meta):
        db_table = 'users_stock_watchlist'
        verbose_name = 'Stock Watchlist'
        verbose_name_plural = 'Stock Watchlists'
        unique_together = ['user', 'stock']
        ordering = ['added_at']
