"""
Scrapers models for GPW Trading Advisor.
Data collection and scraping management.
"""

from django.db import models
from django.utils import timezone
from django.core.validators import URLValidator
from apps.core.models import SoftDeleteModel, StockSymbol, TradingSession
from typing import Any, Dict, List, Optional
import json


class ScrapingSource(SoftDeleteModel):
    """
    Configuration for different scraping sources.
    """
    SOURCE_TYPES = [
        ('stooq', 'Stooq.pl'),
        ('gpw', 'GPW Official'),
        ('bankier', 'Bankier.pl'),
        ('money', 'Money.pl'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    base_url = models.URLField()
    is_enabled = models.BooleanField(default=True, db_index=True)
    scraping_interval = models.PositiveIntegerField(
        default=300,
        help_text="Scraping interval in seconds"
    )
    max_requests_per_minute = models.PositiveIntegerField(default=60)
    timeout_seconds = models.PositiveIntegerField(default=30)
    user_agent = models.TextField(blank=True)
    headers = models.JSONField(default=dict, blank=True)
    
    # Rate limiting
    last_request_time = models.DateTimeField(null=True, blank=True)
    requests_count = models.PositiveIntegerField(default=0)
    requests_reset_time = models.DateTimeField(default=timezone.now)
    
    # Error tracking
    consecutive_errors = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    last_error_time = models.DateTimeField(null=True, blank=True)
    
    # Success tracking
    last_successful_scrape = models.DateTimeField(null=True, blank=True)
    total_successful_requests = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.name} ({self.source_type})"

    @property
    def is_rate_limited(self) -> bool:
        """Check if source is currently rate limited."""
        if not self.last_request_time:
            return False
        
        now = timezone.now()
        
        # Reset requests count if needed
        if now >= self.requests_reset_time:
            self.requests_count = 0
            self.requests_reset_time = now + timezone.timedelta(minutes=1)
            self.save(update_fields=['requests_count', 'requests_reset_time'])
        
        return self.requests_count >= self.max_requests_per_minute

    @property
    def is_healthy(self) -> bool:
        """Check if source is healthy (low error rate)."""
        return self.consecutive_errors < 5

    def record_successful_request(self) -> None:
        """Record a successful scraping request."""
        now = timezone.now()
        self.last_request_time = now
        self.last_successful_scrape = now
        self.requests_count += 1
        self.total_successful_requests += 1
        self.consecutive_errors = 0
        self.save(update_fields=[
            'last_request_time', 'last_successful_scrape', 
            'requests_count', 'total_successful_requests', 'consecutive_errors'
        ])

    def record_failed_request(self, error_message: str) -> None:
        """Record a failed scraping request."""
        now = timezone.now()
        self.last_request_time = now
        self.last_error = error_message
        self.last_error_time = now
        self.requests_count += 1
        self.consecutive_errors += 1
        self.save(update_fields=[
            'last_request_time', 'last_error', 'last_error_time',
            'requests_count', 'consecutive_errors'
        ])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'scrapers_scraping_source'
        verbose_name = 'Scraping Source'
        verbose_name_plural = 'Scraping Sources'
        ordering = ['name']


class ScrapingJob(SoftDeleteModel):
    """
    Individual scraping jobs configuration.
    """
    JOB_TYPES = [
        ('stock_data', 'Stock Data'),
        ('stock_list', 'Stock List'),
        ('indices', 'Market Indices'),
        ('news', 'News'),
        ('fundamentals', 'Fundamentals'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    name = models.CharField(max_length=200)
    job_type = models.CharField(max_length=20, choices=JOB_TYPES)
    source = models.ForeignKey(
        ScrapingSource,
        on_delete=models.CASCADE,
        related_name='jobs'
    )
    stock_symbol = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Specific stock to scrape (if applicable)"
    )
    
    # Configuration
    url_template = models.TextField(help_text="URL template with placeholders")
    css_selectors = models.JSONField(default=dict, help_text="CSS selectors for data extraction")
    xpath_selectors = models.JSONField(default=dict, blank=True)
    
    # Scheduling
    is_scheduled = models.BooleanField(default=True)
    schedule_interval = models.PositiveIntegerField(
        default=300,
        help_text="Interval in seconds between runs"
    )
    next_run_time = models.DateTimeField(default=timezone.now)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    last_run_time = models.DateTimeField(null=True, blank=True)
    last_success_time = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    # Statistics
    total_runs = models.PositiveIntegerField(default=0)
    successful_runs = models.PositiveIntegerField(default=0)
    failed_runs = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.name} ({self.job_type})"

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100

    @property
    def is_due(self) -> bool:
        """Check if job is due to run."""
        if not self.is_scheduled or not self.is_active:
            return False
        return timezone.now() >= self.next_run_time

    def schedule_next_run(self) -> None:
        """Schedule the next run based on interval."""
        self.next_run_time = timezone.now() + timezone.timedelta(
            seconds=self.schedule_interval
        )
        self.save(update_fields=['next_run_time'])

    def mark_started(self) -> None:
        """Mark job as started."""
        self.status = 'running'
        self.last_run_time = timezone.now()
        self.total_runs += 1
        self.save(update_fields=['status', 'last_run_time', 'total_runs'])

    def mark_completed(self) -> None:
        """Mark job as completed successfully."""
        self.status = 'completed'
        self.last_success_time = timezone.now()
        self.successful_runs += 1
        self.last_error = ''
        self.schedule_next_run()
        self.save(update_fields=[
            'status', 'last_success_time', 'successful_runs', 
            'last_error', 'next_run_time'
        ])

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed with error message."""
        self.status = 'failed'
        self.last_error = error_message
        self.failed_runs += 1
        self.schedule_next_run()
        self.save(update_fields=[
            'status', 'last_error', 'failed_runs', 'next_run_time'
        ])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'scrapers_scraping_job'
        verbose_name = 'Scraping Job'
        verbose_name_plural = 'Scraping Jobs'
        ordering = ['-created_at']


class StockData(SoftDeleteModel):
    """
    Raw stock data collected from scraping.
    """
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='stock_data'
    )
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='stock_data'
    )
    source = models.ForeignKey(
        ScrapingSource,
        on_delete=models.CASCADE,
        related_name='stock_data'
    )
    
    # OHLCV data
    open_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    high_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    low_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    close_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    
    # Additional data
    turnover = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    trades_count = models.PositiveIntegerField(null=True, blank=True)
    
    # Price changes
    price_change = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    price_change_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Metadata
    data_timestamp = models.DateTimeField()
    scraped_at = models.DateTimeField(auto_now_add=True)
    raw_data = models.JSONField(default=dict, help_text="Raw scraped data for debugging")
    
    # Quality indicators
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return f"{self.stock.symbol} - {self.trading_session.date} ({self.close_price})"

    @property
    def has_complete_ohlc(self) -> bool:
        """Check if all OHLC values are present."""
        return all([
            self.open_price is not None,
            self.high_price is not None,
            self.low_price is not None,
            self.close_price is not None
        ])

    @property
    def is_suspicious(self) -> bool:
        """Check for suspicious data patterns."""
        if not self.has_complete_ohlc:
            return True
        
        # Check for impossible price relationships
        if (self.high_price is not None and self.low_price is not None and 
            self.high_price < self.low_price):
            return True
        
        # Check for negative prices
        if (self.open_price is not None and self.open_price < 0):
            return True
        if (self.close_price is not None and self.close_price < 0):
            return True
        if (self.high_price is not None and self.high_price < 0):
            return True
        if (self.low_price is not None and self.low_price < 0):
            return True
        
        # Check for negative volume
        if self.volume is not None and self.volume < 0:
            return True
        
        # Check for extreme price changes (more than 50%)
        if (self.price_change_percent is not None and 
            abs(float(self.price_change_percent)) > 50):
            return True
        
        return False

    def validate_data(self) -> List[str]:
        """Validate stock data and return list of errors."""
        errors = []
        
        if not self.has_complete_ohlc:
            errors.append("Missing OHLC data")
        
        if self.is_suspicious:
            errors.append("Suspicious data patterns detected")
        
        if (self.high_price is not None and self.low_price is not None and 
            self.high_price < self.low_price):
            errors.append("High price is less than low price")
        
        # Check for negative prices
        negative_prices = [
            price for price in [self.open_price, self.high_price, self.low_price, self.close_price]
            if price is not None and price < 0
        ]
        if negative_prices:
            errors.append("Negative price values")
        
        if self.volume is not None and self.volume < 0:
            errors.append("Negative volume")
        
        self.validation_errors = errors
        self.is_validated = len(errors) == 0
        self.save(update_fields=['validation_errors', 'is_validated'])
        
        return errors

    class Meta(SoftDeleteModel.Meta):
        db_table = 'scrapers_stock_data'
        verbose_name = 'Stock Data'
        verbose_name_plural = 'Stock Data'
        unique_together = ['stock', 'data_timestamp', 'source']
        ordering = ['-data_timestamp', 'stock__symbol']


class ScrapingLog(models.Model):
    """
    Detailed logging for scraping operations.
    """
    LOG_LEVELS = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]

    job = models.ForeignKey(
        ScrapingJob,
        on_delete=models.CASCADE,
        related_name='logs',
        null=True,
        blank=True
    )
    source = models.ForeignKey(
        ScrapingSource,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    level = models.CharField(max_length=10, choices=LOG_LEVELS)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Request details
    url = models.URLField(blank=True)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    
    # Data extraction
    items_extracted = models.PositiveIntegerField(null=True, blank=True)
    items_saved = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.timestamp} - {self.level.upper()} - {self.message[:50]}"

    class Meta:
        db_table = 'scrapers_scraping_log'
        verbose_name = 'Scraping Log'
        verbose_name_plural = 'Scraping Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['level', 'timestamp']),
            models.Index(fields=['source', 'timestamp']),
        ]


class NewsArticleModel(SoftDeleteModel):
    """
    Model for storing scraped news articles.
    """
    title = models.CharField(max_length=500)
    summary = models.TextField(help_text="Article summary or excerpt")
    content = models.TextField(help_text="Full article content")
    url = models.URLField(unique=True, help_text="Article URL")
    published_date = models.DateTimeField(help_text="Article publication date")
    author = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=100, help_text="Source website name")
    
    # Article categorization
    tags = models.JSONField(default=list, blank=True, help_text="Article tags/categories")
    stock_symbols = models.JSONField(default=list, blank=True, help_text="Related stock symbols")
    
    # Sentiment analysis (for future LLM integration)
    sentiment_score = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Sentiment score from -1 (negative) to +1 (positive)"
    )
    sentiment_analysis = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Detailed sentiment analysis results"
    )
    
    # SEO and metadata
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    
    # Social media metrics (if available)
    social_shares = models.PositiveIntegerField(default=0)
    social_metrics = models.JSONField(default=dict, blank=True)
    
    # Content analysis
    word_count = models.PositiveIntegerField(default=0)
    reading_time_minutes = models.PositiveIntegerField(default=0)
    
    # Scraping metadata
    scraped_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    scraping_source = models.ForeignKey(
        ScrapingSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='news_articles'
    )

    def __str__(self) -> str:
        return f"{self.title} ({self.source})"

    def save(self, *args, **kwargs):
        """Override save to calculate derived fields."""
        # Calculate word count
        if self.content:
            self.word_count = len(self.content.split())
            
        # Estimate reading time (200 words per minute)
        if self.word_count > 0:
            self.reading_time_minutes = max(1, self.word_count // 200)
        
        super().save(*args, **kwargs)

    @property
    def has_stock_relevance(self) -> bool:
        """Check if article mentions any stock symbols."""
        return bool(self.stock_symbols)

    @property
    def is_recent(self) -> bool:
        """Check if article was published in last 24 hours."""
        from datetime import timedelta
        return self.published_date >= timezone.now() - timedelta(hours=24)

    @property
    def relevance_score(self) -> float:
        """Calculate article relevance score."""
        score = 0.0
        
        # Recent articles get higher score
        if self.is_recent:
            score += 0.3
        
        # Articles with stock symbols get higher score
        if self.has_stock_relevance:
            score += 0.4
        
        # Articles with sentiment analysis get higher score
        if self.sentiment_score is not None:
            score += 0.2
        
        # Longer articles (but not too long) get higher score
        if 200 <= self.word_count <= 1000:
            score += 0.1
        
        return min(1.0, score)

    class Meta(SoftDeleteModel.Meta):
        db_table = 'scrapers_news_article'
        verbose_name = 'News Article'
        verbose_name_plural = 'News Articles'
        ordering = ['-published_date']
        indexes = [
            models.Index(fields=['published_date']),
            models.Index(fields=['source', 'published_date']),
            models.Index(fields=['scraped_at']),
        ]


class EventDateChange(models.Model):
    """
    Track date changes for calendar events - CRITICAL for investor sentiment
    Date changes often indicate company delays/advances which affect market sentiment
    """
    CHANGE_TYPE_CHOICES = [
        ('postponed', 'Event Postponed'),
        ('advanced', 'Event Advanced'),
        ('rescheduled', 'Event Rescheduled'),
        ('cancelled', 'Event Cancelled'),
        ('confirmed', 'Date Confirmed'),
    ]
    
    SENTIMENT_IMPACT_CHOICES = [
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
    ]
    
    event = models.ForeignKey(
        'CompanyCalendarEvent',
        on_delete=models.CASCADE,
        related_name='date_changes'
    )
    old_date = models.DateTimeField()
    new_date = models.DateTimeField()
    change_type = models.CharField(max_length=15, choices=CHANGE_TYPE_CHOICES)
    sentiment_impact = models.CharField(max_length=10, choices=SENTIMENT_IMPACT_CHOICES)
    change_reason = models.TextField(blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'scrapers_event_date_changes'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['event', 'detected_at']),
            models.Index(fields=['change_type']),
            models.Index(fields=['sentiment_impact']),
        ]
    
    def __str__(self):
        return f"{self.event.stock_symbol.symbol} - {self.change_type} ({self.old_date.date()} -> {self.new_date.date()})"
    
    def save(self, *args, **kwargs):
        # Auto-determine change type and sentiment impact
        if not self.change_type:
            if self.new_date > self.old_date:
                self.change_type = 'postponed'
                self.sentiment_impact = 'negative'  # Delays are usually negative
            elif self.new_date < self.old_date:
                self.change_type = 'advanced'
                self.sentiment_impact = 'neutral'  # Advances can be neutral/positive
            else:
                self.change_type = 'confirmed'
                self.sentiment_impact = 'neutral'
        
        super().save(*args, **kwargs)


class CompanyCalendarEvent(SoftDeleteModel):
    """
    Model for storing company calendar events and corporate actions.
    """
    EVENT_TYPES = [
        ('earnings', 'Earnings Report'),
        ('dividend', 'Dividend Payment'),
        ('ex_dividend', 'Ex-Dividend Date'),
        ('agm', 'Annual General Meeting'),
        ('conference', 'Investor Conference'),
        ('split', 'Stock Split'),
        ('merger', 'Merger/Acquisition'),
        ('ipo', 'IPO/Listing'),
        ('delisting', 'Delisting'),
        ('other', 'Other Event'),
    ]
    
    IMPACT_LEVELS = [
        ('low', 'Low Impact'),
        ('medium', 'Medium Impact'),
        ('high', 'High Impact'),
        ('critical', 'Critical Impact'),
    ]

    stock_symbol = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='calendar_events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    
    # Event timing
    event_date = models.DateTimeField()
    announcement_date = models.DateTimeField(null=True, blank=True)
    
    # Date change tracking for investor sentiment analysis
    original_date = models.DateTimeField(null=True, blank=True, help_text="Original announced date")
    date_changes_count = models.PositiveIntegerField(default=0)
    last_date_change = models.DateTimeField(null=True, blank=True)
    
    # Event details
    impact_level = models.CharField(max_length=10, choices=IMPACT_LEVELS, default='medium')
    is_confirmed = models.BooleanField(default=False)
    
    # Financial details (for dividends, earnings, etc.)
    dividend_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True
    )
    currency = models.CharField(max_length=3, default='PLN')
    
    # Earnings-specific fields
    estimated_eps = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Estimated earnings per share"
    )
    actual_eps = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Actual earnings per share"
    )
    
    # Source information
    source_url = models.URLField(blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    
    # Market impact tracking
    pre_event_price = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True
    )
    post_event_price = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True
    )
    price_impact_percent = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True
    )

    def __str__(self) -> str:
        return f"{self.stock_symbol.symbol} - {self.title} ({self.event_date.date()})"

    @property
    def is_upcoming(self) -> bool:
        """Check if event is in the future."""
        return self.event_date > timezone.now()

    @property
    def days_until_event(self) -> int:
        """Calculate days until event."""
        if not self.is_upcoming:
            return 0
        
        delta = self.event_date.date() - timezone.now().date()
        return delta.days

    def calculate_price_impact(self):
        """Calculate and store price impact if both pre/post prices available."""
        if self.pre_event_price and self.post_event_price:
            impact = ((self.post_event_price - self.pre_event_price) / self.pre_event_price) * 100
            self.price_impact_percent = impact
            self.save(update_fields=['price_impact_percent'])
    
    def track_date_change(self, old_date, reason="Date modification detected"):
        """Track date changes for sentiment analysis."""
        if old_date != self.event_date:
            EventDateChange.objects.create(
                event=self,
                old_date=old_date,
                new_date=self.event_date,
                change_reason=reason
            )
            self.date_changes_count += 1
            self.last_date_change = timezone.now()
            self.save(update_fields=['date_changes_count', 'last_date_change'])
    
    def save(self, *args, **kwargs):
        # Track date changes on save
        if self.pk:
            try:
                old_event = CompanyCalendarEvent.objects.get(pk=self.pk)
                if old_event.event_date != self.event_date:
                    # Store old date to track after save
                    self._track_old_date = old_event.event_date
            except CompanyCalendarEvent.DoesNotExist:
                pass
        else:
            # Set original date on first save
            if not self.original_date:
                self.original_date = self.event_date
        
        super().save(*args, **kwargs)
        
        # Track date change after save (so we have pk)
        if hasattr(self, '_track_old_date'):
            self.track_date_change(self._track_old_date)
            delattr(self, '_track_old_date')

    class Meta(SoftDeleteModel.Meta):
        db_table = 'scrapers_company_calendar'
        verbose_name = 'Company Calendar Event'
        verbose_name_plural = 'Company Calendar Events'
        ordering = ['event_date']
        indexes = [
            models.Index(fields=['event_date']),
            models.Index(fields=['stock_symbol', 'event_date']),
            models.Index(fields=['event_type', 'event_date']),
        ]


class ESPIReport(SoftDeleteModel):
    """
    Model for storing ESPI/EBI reports from Polish stock exchange.
    """
    REPORT_TYPES = [
        ('espi', 'ESPI - Current Report'),
        ('ebi', 'EBI - Periodic Report'),
        ('rb', 'RB - Quarterly Report'),
        ('rs', 'RS - Annual Report'),
        ('other', 'Other Report'),
    ]
    
    IMPORTANCE_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    stock_symbol = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='espi_reports'
    )
    report_type = models.CharField(max_length=10, choices=REPORT_TYPES)
    report_number = models.CharField(max_length=50)
    title = models.CharField(max_length=500)
    content = models.TextField()
    
    # Publication details
    publication_date = models.DateTimeField()
    effective_date = models.DateTimeField(null=True, blank=True)
    
    # Report classification
    importance_level = models.CharField(max_length=10, choices=IMPORTANCE_LEVELS, default='medium')
    categories = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    
    # Source information
    espi_url = models.URLField()
    pdf_url = models.URLField(blank=True)
    
    # Content analysis
    financial_data = models.JSONField(default=dict, blank=True)
    key_metrics = models.JSONField(default=dict, blank=True)
    
    # LLM analysis results
    summary = models.TextField(blank=True, help_text="AI-generated summary")
    sentiment_analysis = models.JSONField(default=dict, blank=True)
    market_impact_prediction = models.TextField(blank=True)
    
    # Market reaction tracking
    price_before = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    price_after_1h = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    price_after_24h = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    volume_impact = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.stock_symbol.symbol} - {self.report_type.upper()} {self.report_number}"

    @property
    def is_recent(self) -> bool:
        """Check if report was published in last 48 hours."""
        from datetime import timedelta
        return self.publication_date >= timezone.now() - timedelta(hours=48)

    @property
    def has_financial_impact(self) -> bool:
        """Check if report likely has financial impact."""
        impact_keywords = [
            'zysk', 'strata', 'przychody', 'wydatki', 'dywidenda', 
            'połączenie', 'przejęcie', 'emisja', 'wykup'
        ]
        content_lower = self.content.lower()
        return any(keyword in content_lower for keyword in impact_keywords)

    class Meta(SoftDeleteModel.Meta):
        db_table = 'scrapers_espi_report'
        verbose_name = 'ESPI Report'
        verbose_name_plural = 'ESPI Reports'
        ordering = ['-publication_date']
        unique_together = ['stock_symbol', 'report_number']
        indexes = [
            models.Index(fields=['publication_date']),
            models.Index(fields=['stock_symbol', 'publication_date']),
            models.Index(fields=['report_type', 'publication_date']),
        ]
