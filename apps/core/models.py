"""
Core models for GPW Trading Advisor.
Base classes and common functionality shared across apps.
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import time, timedelta
from typing import Any, Dict, Optional, Tuple


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides self-updating 
    'created_at' and 'updated_at' fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActiveManager(models.Manager):
    """Manager that returns only active objects."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteModel(TimeStampedModel):
    """
    Abstract base model that provides soft delete functionality.
    Objects are marked as inactive instead of being deleted.
    """
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()  # Default manager
    active = ActiveManager()   # Only active objects

    class Meta:  # type: ignore[misc]
        abstract = True

    def delete(self, using: Optional[str] = None, keep_parents: bool = False) -> Tuple[int, Dict[str, int]]:
        """Soft delete: mark as inactive instead of deleting."""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=['is_active', 'deleted_at', 'updated_at'])
        # Return Django's expected format for delete operation
        return (1, {self._meta.label: 1})

    def hard_delete(self, using: Optional[str] = None, keep_parents: bool = False) -> Tuple[int, Dict[str, int]]:
        """Actually delete the object from database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self) -> None:
        """Restore a soft-deleted object."""
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=['is_active', 'deleted_at', 'updated_at'])


class StockSymbol(SoftDeleteModel):
    """
    Model representing stock symbols available for trading.
    """
    symbol = models.CharField(
        max_length=10, 
        unique=True, 
        db_index=True,
        help_text="Stock symbol (e.g., PKN, CDR, PKO)"
    )
    name = models.CharField(
        max_length=200,
        help_text="Full company name"
    )
    
    # Legacy field - will be replaced by industries relationship
    sector = models.CharField(
        max_length=100,
        blank=True,
        help_text="Industry sector (legacy field)"
    )
    
    # New market and industry relationships
    market = models.ForeignKey(
        'core.Market',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stocks',
        help_text="Stock market where company is listed"
    )
    
    primary_industry = models.ForeignKey(
        'core.Industry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_stocks',
        help_text="Primary industry/sector of the company"
    )
    
    industries = models.ManyToManyField(
        'core.Industry',
        blank=True,
        related_name='stocks',
        help_text="All industries the company operates in"
    )
    
    # Company details
    isin_code = models.CharField(
        max_length=12,
        blank=True,
        help_text="International Securities Identification Number"
    )
    
    market_cap = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Market capitalization in PLN"
    )
    
    # Business profile
    business_description = models.TextField(
        blank=True,
        help_text="Brief description of company's business"
    )
    
    website = models.URLField(
        blank=True,
        help_text="Company's official website"
    )
    
    # AI-related keywords for news classification
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Keywords to help AI identify news related to this company"
    )
    
    # Monitoring settings
    is_monitored = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this stock is actively monitored"
    )
    
    news_monitoring_enabled = models.BooleanField(
        default=True,
        help_text="Whether to monitor news for this stock"
    )
    
    # External data sources
    stooq_url = models.URLField(
        blank=True,
        help_text="URL for scraping data from stooq.pl"
    )
    
    bankier_symbol = models.CharField(
        max_length=20,
        blank=True,
        help_text="Symbol used on bankier.pl (e.g., 11BIT, PKOBP)"
    )
    
    # Last AI classification update
    last_ai_analysis = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this stock was last analyzed by AI for news relevance"
    )

    def __str__(self) -> str:
        return f"{self.symbol} - {self.name}"

    @property
    def display_name(self) -> str:
        """Return formatted display name."""
        return f"{self.symbol} ({self.name})"

    class Meta(SoftDeleteModel.Meta):
        db_table = 'core_stock_symbol'
        verbose_name = 'Stock Symbol'
        verbose_name_plural = 'Stock Symbols'
        ordering = ['symbol']


class TradingSession(SoftDeleteModel):
    """
    Model representing a trading session (day).
    """
    date = models.DateField(unique=True, db_index=True)
    is_trading_day = models.BooleanField(default=True)
    market_open_time = models.TimeField(default=time(9, 0))
    market_close_time = models.TimeField(default=time(17, 30))
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Trading Session {self.date}"

    @property
    def is_open(self) -> bool:
        """Check if trading session is currently open."""
        if not self.is_trading_day:
            return False
        
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        return (current_date == self.date and 
                self.market_open_time <= current_time <= self.market_close_time)

    @classmethod
    def get_current_session(cls) -> Optional['TradingSession']:
        """Get current trading session if exists."""
        today = timezone.now().date()
        try:
            return cls.active.get(date=today)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_session_for_date(cls, date: Any, is_trading_day: bool = True) -> 'TradingSession':
        """Create a new trading session for given date."""
        return cls.objects.create(
            date=date,
            is_trading_day=is_trading_day
        )

    class Meta(SoftDeleteModel.Meta):
        db_table = 'core_trading_session'
        verbose_name = 'Trading Session'
        verbose_name_plural = 'Trading Sessions'
        ordering = ['-date']


class Market(models.Model):
    """
    Stock market definitions (Main Market, NewConnect, Catalyst, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Market characteristics
    is_regulated = models.BooleanField(default=True)
    min_market_cap = models.BigIntegerField(null=True, blank=True, help_text="Minimum market cap in PLN")
    trading_hours_start = models.TimeField(null=True, blank=True)
    trading_hours_end = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_markets'
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.code})"


class Industry(models.Model):
    """
    Industry/sector classification for companies
    """
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Industry hierarchy
    parent_industry = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='sub_industries'
    )
    
    # Industry characteristics
    is_cyclical = models.BooleanField(default=False)
    volatility_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low Volatility'),
            ('medium', 'Medium Volatility'),
            ('high', 'High Volatility'),
        ],
        default='medium'
    )
    
    # Keywords for AI classification
    keywords = models.JSONField(default=list, blank=True, help_text="Keywords for automatic classification")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_industries'
        ordering = ['name']
        verbose_name_plural = 'Industries'
        
    def __str__(self):
        if self.parent_industry:
            return f"{self.parent_industry.name} > {self.name}"
        return self.name
        
    @property
    def full_path(self):
        """Get full industry path"""
        if self.parent_industry:
            return f"{self.parent_industry.full_path} > {self.name}"
        return self.name


class LLMProvider(models.Model):
    """
    Configuration for LLM providers (OpenAI, OLLAMA, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('openai', 'OpenAI'),
            ('ollama', 'OLLAMA'),
            ('huggingface', 'HuggingFace'),
            ('anthropic', 'Anthropic'),
        ]
    )
    
    # Configuration
    api_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    model_name = models.CharField(max_length=100)
    
    # Performance settings
    max_tokens = models.IntegerField(default=1000)
    temperature = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=False)
    last_check = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    requests_count = models.IntegerField(default=0)
    total_tokens_used = models.BigIntegerField(default=0)
    last_request = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_llm_providers'
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.provider_type})"


class NewsClassification(models.Model):
    """
    AI-powered classification results for news articles
    """
    # Link to news article
    article = models.OneToOneField(
        'news.NewsArticleModel',
        on_delete=models.CASCADE,
        related_name='ai_classification'
    )
    
    # LLM provider used
    llm_provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.SET_NULL,
        null=True,
        related_name='classifications'
    )
    
    # AI Analysis Results
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('very_positive', 'Very Positive'),
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
            ('very_negative', 'Very Negative'),
        ],
        null=True,
        blank=True
    )
    sentiment_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)]
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Industry classification
    detected_industries = models.ManyToManyField(
        Industry,
        blank=True,
        related_name='news_classifications'
    )
    primary_industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_news_classifications'
    )
    
    # Market impact assessment
    market_impact = models.CharField(
        max_length=20,
        choices=[
            ('very_high', 'Very High Impact'),
            ('high', 'High Impact'),
            ('medium', 'Medium Impact'),
            ('low', 'Low Impact'),
            ('minimal', 'Minimal Impact'),
        ],
        null=True,
        blank=True
    )
    
    # AI-extracted entities
    mentioned_companies = models.JSONField(default=list, blank=True)
    mentioned_people = models.JSONField(default=list, blank=True)
    mentioned_locations = models.JSONField(default=list, blank=True)
    key_topics = models.JSONField(default=list, blank=True)
    
    # AI reasoning
    ai_summary = models.TextField(blank=True)
    ai_reasoning = models.TextField(blank=True)
    key_phrases = models.JSONField(default=list, blank=True)
    
    # Processing metadata
    processing_time_ms = models.IntegerField(null=True, blank=True)
    tokens_used = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_news_classifications'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Classification for: {self.article.title[:50]}..."


class IndustrySentiment(models.Model):
    """
    Sentiment analysis per industry for a news article
    """
    classification = models.ForeignKey(
        NewsClassification,
        on_delete=models.CASCADE,
        related_name='industry_sentiments'
    )
    industry = models.ForeignKey(
        Industry,
        on_delete=models.CASCADE,
        related_name='sentiment_analyses'
    )
    
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('very_positive', 'Very Positive'),
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
            ('very_negative', 'Very Negative'),
        ]
    )
    sentiment_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Sentiment score from investor perspective (-1 to 1)"
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="AI confidence in this sentiment analysis"
    )
    reasoning = models.TextField(
        help_text="AI reasoning for this industry-specific sentiment"
    )
    
    class Meta:
        db_table = 'core_industry_sentiments'
        unique_together = ['classification', 'industry']
        ordering = ['-sentiment_score']
        
    def __str__(self):
        return f"{self.industry.name}: {self.sentiment} ({self.sentiment_score})"


class StockSentiment(models.Model):
    """
    Sentiment analysis per stock for a news article
    """
    classification = models.ForeignKey(
        NewsClassification,
        on_delete=models.CASCADE,
        related_name='stock_sentiments'
    )
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='sentiment_analyses'
    )
    
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('very_positive', 'Very Positive'),
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
            ('very_negative', 'Very Negative'),
        ]
    )
    sentiment_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Sentiment score from investor perspective (-1 to 1)"
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="AI confidence in this sentiment analysis"
    )
    reasoning = models.TextField(
        help_text="AI reasoning for this stock-specific sentiment"
    )
    relevance_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How relevant is this news to the stock"
    )
    
    class Meta:
        db_table = 'core_stock_sentiments'
        unique_together = ['classification', 'stock']
        ordering = ['-relevance_score', '-sentiment_score']
        
    def __str__(self):
        return f"{self.stock.symbol}: {self.sentiment} ({self.sentiment_score})"


# =============================================================================
# SCHEDULING MODELS
# =============================================================================

class ScrapingSchedule(models.Model):
    """
    Configuration for automated scraping schedules
    """
    SCRAPER_TYPES = [
        ('news_rss', 'News RSS Feeds'),
        ('stock_prices', 'Stock Prices'),
        ('calendar_events', 'Calendar Events'),
        ('espi_reports', 'ESPI Reports'),
    ]
    
    FREQUENCY_UNITS = [
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
    ]
    
    name = models.CharField(max_length=100, help_text="Descriptive name for this schedule")
    scraper_type = models.CharField(max_length=20, choices=SCRAPER_TYPES)
    
    # Frequency settings
    is_active = models.BooleanField(default=True)
    frequency_value = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        help_text="How often to run (1-1440)"
    )
    frequency_unit = models.CharField(max_length=10, choices=FREQUENCY_UNITS)
    
    # Time restrictions
    active_hours_start = models.TimeField(
        default=time(8, 0),
        help_text="Start of active hours (e.g., 08:00)"
    )
    active_hours_end = models.TimeField(
        default=time(18, 0),
        help_text="End of active hours (e.g., 18:00)"
    )
    
    # Day restrictions
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
    
    # Holiday handling
    skip_polish_holidays = models.BooleanField(
        default=True,
        help_text="Skip execution on Polish public holidays"
    )
    skip_gpw_holidays = models.BooleanField(
        default=True,
        help_text="Skip execution on GPW non-trading days"
    )
    
    # Advanced settings
    max_retries = models.IntegerField(default=3)
    retry_delay_minutes = models.IntegerField(default=5)
    timeout_minutes = models.IntegerField(default=10)
    
    # Configuration specific to scraper type
    scraper_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional configuration specific to scraper type"
    )
    
    # Execution tracking
    last_run = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    failure_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_scraping_schedules'
        ordering = ['scraper_type', 'name']
        
    def __str__(self):
        return f"{self.get_scraper_type_display()}: {self.name}"
    
    @property
    def frequency_description(self):
        """Human readable frequency description"""
        if self.frequency_unit == 'minutes':
            if self.frequency_value == 1:
                return "Every minute"
            else:
                return f"Every {self.frequency_value} minutes"
        elif self.frequency_unit == 'hours':
            if self.frequency_value == 1:
                return "Every hour"
            else:
                return f"Every {self.frequency_value} hours"
        else:  # days
            if self.frequency_value == 1:
                return "Daily"
            else:
                return f"Every {self.frequency_value} days"
    
    @property
    def active_days(self):
        """List of active days"""
        days = []
        if self.monday: days.append("Mon")
        if self.tuesday: days.append("Tue")
        if self.wednesday: days.append("Wed")
        if self.thursday: days.append("Thu")
        if self.friday: days.append("Fri")
        if self.saturday: days.append("Sat")
        if self.sunday: days.append("Sun")
        return days
    
    def should_run_now(self):
        """Check if scraper should run at current time"""
        now = timezone.now()
        
        # Convert to local timezone (Europe/Warsaw)
        local_now = timezone.localtime(now)
        
        # Check if active
        if not self.is_active:
            return False
            
        # Check day of week
        weekday = local_now.weekday()  # 0=Monday, 6=Sunday
        day_active = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ][weekday]
        
        if not day_active:
            return False
            
        # Check time of day - use local time
        current_time = local_now.time()
        if not (self.active_hours_start <= current_time <= self.active_hours_end):
            return False
            
        # Check if it's time for next run
        if self.next_run and now < self.next_run:
            return False
            
        # Check holidays (simplified - could be enhanced with actual holiday API)
        if self.skip_polish_holidays and self.is_polish_holiday(now.date()):
            return False
            
        return True
    
    def calculate_next_run(self):
        """Calculate next run time based on frequency and restrictions"""
        now = timezone.now()
        
        if self.frequency_unit == 'minutes':
            delta = timedelta(minutes=self.frequency_value)
        elif self.frequency_unit == 'hours':
            delta = timedelta(hours=self.frequency_value)
        else:  # days
            delta = timedelta(days=self.frequency_value)
            
        next_run = now + delta
        
        # Adjust to active hours if necessary
        next_run = self.adjust_to_active_hours(next_run)
        
        self.next_run = next_run
        self.save(update_fields=['next_run'])
        return next_run
    
    def adjust_to_active_hours(self, dt):
        """Adjust datetime to fall within active hours and days"""
        # Convert to local timezone for comparison with active hours
        local_dt = timezone.localtime(dt)
        
        # If outside active hours, move to next active period
        if local_dt.time() < self.active_hours_start:
            local_dt = local_dt.replace(hour=self.active_hours_start.hour, 
                           minute=self.active_hours_start.minute, 
                           second=0, microsecond=0)
        elif local_dt.time() > self.active_hours_end:
            # Move to next day's start time
            local_dt = local_dt + timedelta(days=1)
            local_dt = local_dt.replace(hour=self.active_hours_start.hour,
                           minute=self.active_hours_start.minute,
                           second=0, microsecond=0)
        
        # Check if day is active
        weekday = local_dt.weekday()
        active_days = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ]
        
        # Find next active day
        days_ahead = 0
        while not active_days[(weekday + days_ahead) % 7] and days_ahead < 7:
            days_ahead += 1
            
        if days_ahead > 0:
            local_dt = local_dt + timedelta(days=days_ahead)
            local_dt = local_dt.replace(hour=self.active_hours_start.hour,
                           minute=self.active_hours_start.minute,
                           second=0, microsecond=0)
        
        # Convert back to UTC for storage
        return local_dt
    
    def is_polish_holiday(self, date):
        """Check if date is Polish public holiday (simplified implementation)"""
        # This is a simplified version - in production you'd use a proper holiday library
        
        # New Year's Day
        if date.month == 1 and date.day == 1:
            return True
            
        # May Day
        if date.month == 5 and date.day == 1:
            return True
            
        # Constitution Day
        if date.month == 5 and date.day == 3:
            return True
            
        # Independence Day
        if date.month == 11 and date.day == 11:
            return True
            
        # Christmas
        if date.month == 12 and date.day in [25, 26]:
            return True
            
        return False
    
    def mark_execution(self, success=True):
        """Mark that scraper was executed"""
        now = timezone.now()
        self.last_run = now
        
        if success:
            self.last_success = now
            self.failure_count = 0
        else:
            self.failure_count += 1
            
        self.calculate_next_run()
        self.save()


class ScrapingExecution(models.Model):
    """
    Log of scraping executions
    """
    schedule = models.ForeignKey(
        ScrapingSchedule,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    success = models.BooleanField(default=False)
    items_processed = models.IntegerField(default=0)
    items_created = models.IntegerField(default=0)
    items_updated = models.IntegerField(default=0)
    
    error_message = models.TextField(blank=True)
    execution_details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'core_scraping_executions'
        ordering = ['-started_at']
        
    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.schedule.name} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def duration(self):
        """Execution duration in seconds"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
