"""
Scheduling models for automated scraping tasks
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import time, datetime, timedelta
import json


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
        
        # Check if active
        if not self.is_active:
            return False
            
        # Check day of week
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        day_active = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ][weekday]
        
        if not day_active:
            return False
            
        # Check time of day
        current_time = now.time()
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
        # If outside active hours, move to next active period
        if dt.time() < self.active_hours_start:
            dt = dt.replace(hour=self.active_hours_start.hour, 
                           minute=self.active_hours_start.minute, 
                           second=0, microsecond=0)
        elif dt.time() > self.active_hours_end:
            # Move to next day's start time
            dt = dt + timedelta(days=1)
            dt = dt.replace(hour=self.active_hours_start.hour,
                           minute=self.active_hours_start.minute,
                           second=0, microsecond=0)
        
        # Check if day is active
        weekday = dt.weekday()
        active_days = [
            self.monday, self.tuesday, self.wednesday, self.thursday,
            self.friday, self.saturday, self.sunday
        ]
        
        # Find next active day
        days_ahead = 0
        while not active_days[(weekday + days_ahead) % 7] and days_ahead < 7:
            days_ahead += 1
            
        if days_ahead > 0:
            dt = dt + timedelta(days=days_ahead)
            dt = dt.replace(hour=self.active_hours_start.hour,
                           minute=self.active_hours_start.minute,
                           second=0, microsecond=0)
            
        return dt
    
    def is_polish_holiday(self, date):
        """Check if date is Polish public holiday (simplified implementation)"""
        # This is a simplified version - in production you'd use a proper holiday library
        # or API like holidays library: pip install holidays
        
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
