"""
News and Events Models with Event Change Tracking
Enhanced for investor sentiment analysis
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from typing import Optional, Dict, Any
import json

User = get_user_model()


class NewsSource(models.Model):
    """
    News source configuration
    """
    name = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    type = models.CharField(max_length=20, choices=[
        ('rss', 'RSS Feed'),
        ('html', 'HTML Scraping'),
        ('api', 'API'),
    ])
    is_active = models.BooleanField(default=True)
    scraping_config = models.JSONField(default=dict, blank=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'news_sources'
    
    def __str__(self):
        return f"{self.name} ({self.type})"


class NewsArticleModel(models.Model):
    """
    News articles with sentiment analysis capability
    """
    IMPACT_CHOICES = [
        ('high', 'High Impact'),
        ('medium', 'Medium Impact'), 
        ('low', 'Low Impact'),
        ('unknown', 'Unknown Impact'),
    ]
    
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
        ('unknown', 'Unknown'),
    ]
    
    title = models.CharField(max_length=500)
    content = models.TextField()
    url = models.URLField(unique=True)
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name='articles')
    
    # Stock associations
    mentioned_stocks = models.ManyToManyField('core.StockSymbol', blank=True, related_name='news_mentions')
    primary_stock = models.ForeignKey('core.StockSymbol', on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_news')
    
    # Analysis fields
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, default='unknown')
    sentiment_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)])
    market_impact = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='unknown')
    impact_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    # Keywords and tags
    keywords = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Metadata
    published_date = models.DateTimeField()
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analysis status
    is_analyzed = models.BooleanField(default=False)
    analysis_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'news_articles'
        ordering = ['-published_date']
        indexes = [
            models.Index(fields=['published_date']),
            models.Index(fields=['sentiment']),
            models.Index(fields=['market_impact']),
            models.Index(fields=['source']),
        ]
    
    def __str__(self):
        return f"{self.title[:50]}... ({self.source.name})"


class CompanyCalendarEvent(models.Model):
    """
    Company calendar events with change tracking for investor sentiment analysis
    """
    EVENT_TYPE_CHOICES = [
        ('dividend', 'Dividend Payment'),
        ('earnings', 'Earnings Report'),
        ('meeting', 'Shareholder Meeting'),
        ('conference', 'Conference Call'),
        ('announcement', 'Important Announcement'),
        ('other', 'Other Event'),
    ]
    
    IMPACT_CHOICES = [
        ('high', 'High Impact'),
        ('medium', 'Medium Impact'),
        ('low', 'Low Impact'),
        ('unknown', 'Unknown Impact'),
    ]
    
    stock = models.ForeignKey('core.StockSymbol', on_delete=models.CASCADE, related_name='calendar_events')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    
    # Date tracking - CRUCIAL for sentiment analysis
    event_date = models.DateField()
    original_date = models.DateField()  # Track original announced date
    date_changes_count = models.PositiveIntegerField(default=0)
    
    # Market impact assessment
    market_impact = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='unknown')
    impact_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    # Financial data (for dividend events)
    dividend_amount = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    dividend_currency = models.CharField(max_length=3, default='PLN')
    
    # Source tracking
    source_url = models.URLField(null=True, blank=True)
    source_name = models.CharField(max_length=100, default='Bankier.pl')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    
    # Status tracking
    is_confirmed = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'company_calendar_events'
        ordering = ['event_date', 'stock__symbol']
        indexes = [
            models.Index(fields=['event_date']),
            models.Index(fields=['event_type']),
            models.Index(fields=['market_impact']),
            models.Index(fields=['stock']),
            models.Index(fields=['is_confirmed']),
        ]
        unique_together = ['stock', 'event_date', 'event_type', 'title']
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.title} ({self.event_date})"
    
    def save(self, *args, **kwargs):
        # Track date changes
        if self.pk:
            old_event = CompanyCalendarEvent.objects.get(pk=self.pk)
            if old_event.event_date != self.event_date:
                self.date_changes_count += 1
                # Create change history record
                EventDateChange.objects.create(
                    event=self,
                    old_date=old_event.event_date,
                    new_date=self.event_date,
                    change_reason='Date modification detected'
                )
        else:
            # Set original date on first save
            self.original_date = self.event_date
        
        super().save(*args, **kwargs)


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
    
    event = models.ForeignKey(CompanyCalendarEvent, on_delete=models.CASCADE, related_name='date_changes')
    old_date = models.DateField()
    new_date = models.DateField(null=True, blank=True)  # Null if cancelled
    
    change_type = models.CharField(max_length=15, choices=CHANGE_TYPE_CHOICES)
    change_reason = models.TextField(blank=True)
    
    # Market sentiment impact
    sentiment_impact = models.CharField(max_length=10, choices=[
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
    ], default='neutral')
    
    # Metadata
    detected_at = models.DateTimeField(auto_now_add=True)
    source_url = models.URLField(null=True, blank=True)
    
    class Meta:
        db_table = 'event_date_changes'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['detected_at']),
            models.Index(fields=['change_type']),
            models.Index(fields=['sentiment_impact']),
        ]
    
    def __str__(self):
        return f"{self.event.stock.symbol} - {self.change_type}: {self.old_date} → {self.new_date}"
    
    def days_difference(self) -> Optional[int]:
        """Calculate days between old and new date"""
        if self.new_date:
            return (self.new_date - self.old_date).days
        return None
    
    def is_delay(self) -> bool:
        """Check if this is a delay (negative sentiment)"""
        return bool(self.new_date and self.new_date > self.old_date)
    
    def is_advancement(self) -> bool:
        """Check if this is an advancement (potentially positive sentiment)"""
        return bool(self.new_date and self.new_date < self.old_date)


class ESPIReport(models.Model):
    """
    ESPI regulatory reports from GPW
    """
    REPORT_TYPE_CHOICES = [
        ('RB', 'Raporty bieżące (Current Reports)'),
        ('RP', 'Raporty okresowe (Periodic Reports)'),
        ('RS', 'Raporty specjalne (Special Reports)'),
        ('UNI', 'Komunikaty uniwersalne (Universal Communications)'),
    ]
    
    IMPORTANCE_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    stock = models.ForeignKey('core.StockSymbol', on_delete=models.CASCADE, related_name='espi_reports')
    report_number = models.CharField(max_length=50)
    title = models.CharField(max_length=500)
    content = models.TextField()
    
    report_type = models.CharField(max_length=3, choices=REPORT_TYPE_CHOICES)
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default='medium')
    
    # URL and source
    source_url = models.URLField()
    attachment_urls = models.JSONField(default=list, blank=True)
    
    # Dates
    publication_date = models.DateTimeField()
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analysis
    keywords = models.JSONField(default=list, blank=True)
    sentiment = models.CharField(max_length=10, choices=[
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
        ('unknown', 'Unknown'),
    ], default='unknown')
    
    # Market impact
    market_impact_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    class Meta:
        db_table = 'espi_reports'
        ordering = ['-publication_date']
        indexes = [
            models.Index(fields=['publication_date']),
            models.Index(fields=['report_type']),
            models.Index(fields=['importance']),
            models.Index(fields=['stock']),
        ]
        unique_together = ['stock', 'report_number']
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.report_number}: {self.title[:50]}..."


class CalendarScrapingJob(models.Model):
    """
    Track calendar scraping jobs with date range selection
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Date range selection
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Source configuration
    source_urls = models.JSONField(default=list)  # List of URLs to scrape
    scraping_config = models.JSONField(default=dict, blank=True)
    
    # Execution tracking
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    events_found = models.PositiveIntegerField(default=0)
    events_created = models.PositiveIntegerField(default=0)
    events_updated = models.PositiveIntegerField(default=0)
    date_changes_detected = models.PositiveIntegerField(default=0)
    
    # Logs and errors
    logs = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scraping_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'calendar_scraping_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"
    
    def duration(self) -> Optional[str]:
        """Calculate job duration"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return str(delta)
        return None
    
    def success_rate(self) -> float:
        """Calculate success rate of events creation"""
        if self.events_found > 0:
            return (self.events_created + self.events_updated) / self.events_found
        return 0.0
