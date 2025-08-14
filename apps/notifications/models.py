"""
Notifications models for GPW Trading Advisor.
Email and Telegram notification management.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.models import SoftDeleteModel, StockSymbol
from apps.analysis.models import TradingSignal, MarketAnalysis
from typing import Any, Dict, List, Optional

User = get_user_model()


class NotificationTemplate(SoftDeleteModel):
    """
    Templates for different types of notifications.
    """
    TEMPLATE_TYPES = [
        ('email_daily_summary', 'Email Daily Summary'),
        ('email_signal_alert', 'Email Signal Alert'),
        ('email_price_alert', 'Email Price Alert'),
        ('telegram_daily_summary', 'Telegram Daily Summary'),
        ('telegram_signal_alert', 'Telegram Signal Alert'),
        ('telegram_price_alert', 'Telegram Price Alert'),
        ('email_welcome', 'Email Welcome'),
        ('email_subscription_expiry', 'Email Subscription Expiry'),
    ]

    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, unique=True)
    subject_template = models.CharField(
        max_length=300,
        help_text="Template for email subject or Telegram title"
    )
    content_template = models.TextField(
        help_text="Template content with placeholders"
    )
    
    # Template variables documentation
    available_variables = models.JSONField(
        default=list,
        help_text="List of available template variables"
    )
    
    # Configuration
    is_enabled = models.BooleanField(default=True)
    is_html = models.BooleanField(default=True, help_text="Whether template contains HTML")
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.template_type})"

    def render(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Render template with provided context."""
        try:
            subject = self.subject_template.format(**context)
            content = self.content_template.format(**context)
            
            # Update usage statistics
            self.usage_count += 1
            self.last_used = timezone.now()
            self.save(update_fields=['usage_count', 'last_used'])
            
            return {
                'subject': subject,
                'content': content,
                'is_html': self.is_html
            }
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    @classmethod
    def get_template(cls, template_type: str) -> Optional['NotificationTemplate']:
        """Get active template by type."""
        try:
            return cls.active.get(template_type=template_type, is_enabled=True)
        except cls.DoesNotExist:
            return None

    class Meta(SoftDeleteModel.Meta):
        db_table = 'notifications_template'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        ordering = ['template_type']


class Notification(SoftDeleteModel):
    """
    Individual notifications sent to users.
    """
    NOTIFICATION_TYPES = [
        ('daily_summary', 'Daily Summary'),
        ('signal_alert', 'Signal Alert'),
        ('price_alert', 'Price Alert'),
        ('system_alert', 'System Alert'),
        ('welcome', 'Welcome'),
        ('subscription_expiry', 'Subscription Expiry'),
    ]

    DELIVERY_METHODS = [
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('both', 'Both'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_METHODS)
    
    # Content
    subject = models.CharField(max_length=300)
    content = models.TextField()
    is_html = models.BooleanField(default=True)
    
    # Delivery status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery tracking
    email_message_id = models.CharField(max_length=200, blank=True)
    telegram_message_id = models.CharField(max_length=100, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    
    # Related objects
    related_signal = models.ForeignKey(
        TradingSignal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Metadata
    template_used = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    context_data = models.JSONField(default=dict, help_text="Template context data")

    def __str__(self) -> str:
        return f"{self.user.username} - {self.notification_type} - {self.status}"

    @property
    def is_deliverable(self) -> bool:
        """Check if notification can be delivered."""
        # Check user preferences
        prefs = getattr(self.user, 'notification_preferences', None)
        if not prefs:
            return False
        
        # Check delivery method availability
        if self.delivery_method in ['email', 'both'] and not prefs.email_enabled:
            return False
        
        if self.delivery_method in ['telegram', 'both'] and not prefs.telegram_enabled:
            return False
        
        # Check quiet hours
        if not prefs.can_send_notifications:
            return False
        
        return True

    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return self.retry_count < self.max_retries and self.status == 'failed'

    def mark_as_sending(self) -> None:
        """Mark notification as being sent."""
        self.status = 'sending'
        self.save(update_fields=['status'])

    def mark_as_sent(self, message_id: str = '', delivery_method: str = '') -> None:
        """Mark notification as successfully sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        
        if delivery_method == 'email' and message_id:
            self.email_message_id = message_id
        elif delivery_method == 'telegram' and message_id:
            self.telegram_message_id = message_id
        
        self.save(update_fields=['status', 'sent_at', 'email_message_id', 'telegram_message_id'])

    def mark_as_failed(self, error_message: str) -> None:
        """Mark notification as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])

    def schedule_retry(self, delay_minutes: int = 30) -> None:
        """Schedule notification for retry."""
        if self.can_retry:
            self.status = 'pending'
            self.scheduled_at = timezone.now() + timezone.timedelta(minutes=delay_minutes)
            self.save(update_fields=['status', 'scheduled_at'])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'notifications_notification'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['notification_type', 'created_at']),
        ]


class NotificationQueue(models.Model):
    """
    Queue for processing notifications.
    """
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    notification = models.OneToOneField(
        Notification,
        on_delete=models.CASCADE,
        related_name='queue_entry'
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    # Processing
    is_processing = models.BooleanField(default=False)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    worker_id = models.CharField(max_length=100, blank=True)
    
    # Scheduling
    execute_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Queue: {self.notification} (Priority: {self.priority})"

    @property
    def is_ready(self) -> bool:
        """Check if notification is ready to be processed."""
        return (timezone.now() >= self.execute_at and 
                not self.is_processing and
                self.notification.status == 'pending')

    def mark_processing(self, worker_id: str) -> None:
        """Mark as being processed by worker."""
        self.is_processing = True
        self.processing_started_at = timezone.now()
        self.worker_id = worker_id
        self.save(update_fields=['is_processing', 'processing_started_at', 'worker_id'])

    def release_lock(self) -> None:
        """Release processing lock."""
        self.is_processing = False
        self.processing_started_at = None
        self.worker_id = ''
        self.save(update_fields=['is_processing', 'processing_started_at', 'worker_id'])

    @classmethod
    def get_next_notification(cls, worker_id: str) -> Optional['NotificationQueue']:
        """Get next notification to process."""
        # Clean up stale locks (older than 10 minutes)
        stale_cutoff = timezone.now() - timezone.timedelta(minutes=10)
        cls.objects.filter(
            is_processing=True,
            processing_started_at__lt=stale_cutoff
        ).update(
            is_processing=False,
            processing_started_at=None,
            worker_id=''
        )
        
        # Get next available notification
        queue_entry = cls.objects.filter(
            execute_at__lte=timezone.now(),
            is_processing=False,
            notification__status='pending'
        ).order_by('priority', 'execute_at').first()
        
        if queue_entry:
            queue_entry.mark_processing(worker_id)
        
        return queue_entry

    class Meta:
        db_table = 'notifications_queue'
        verbose_name = 'Notification Queue'
        verbose_name_plural = 'Notification Queue'
        ordering = ['priority', 'execute_at']
        indexes = [
            models.Index(fields=['priority', 'execute_at']),
            models.Index(fields=['is_processing', 'execute_at']),
        ]


class NotificationStats(models.Model):
    """
    Statistics for notification delivery.
    """
    date = models.DateField(unique=True)
    
    # Email stats
    emails_sent = models.PositiveIntegerField(default=0)
    emails_failed = models.PositiveIntegerField(default=0)
    emails_bounced = models.PositiveIntegerField(default=0)
    emails_opened = models.PositiveIntegerField(default=0)
    emails_clicked = models.PositiveIntegerField(default=0)
    
    # Telegram stats
    telegram_sent = models.PositiveIntegerField(default=0)
    telegram_failed = models.PositiveIntegerField(default=0)
    telegram_read = models.PositiveIntegerField(default=0)
    
    # By notification type
    daily_summaries_sent = models.PositiveIntegerField(default=0)
    signal_alerts_sent = models.PositiveIntegerField(default=0)
    price_alerts_sent = models.PositiveIntegerField(default=0)
    system_alerts_sent = models.PositiveIntegerField(default=0)
    
    # Performance
    avg_delivery_time_seconds = models.PositiveIntegerField(default=0)
    queue_processing_time_seconds = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Notification Stats - {self.date}"

    @property
    def total_sent(self) -> int:
        """Total notifications sent."""
        return self.emails_sent + self.telegram_sent

    @property
    def total_failed(self) -> int:
        """Total notifications failed."""
        return self.emails_failed + self.telegram_failed

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.total_sent + self.total_failed
        if total == 0:
            return 0.0
        return (self.total_sent / total) * 100

    @property
    def email_open_rate(self) -> float:
        """Calculate email open rate percentage."""
        if self.emails_sent == 0:
            return 0.0
        return (self.emails_opened / self.emails_sent) * 100

    @property
    def email_click_rate(self) -> float:
        """Calculate email click rate percentage."""
        if self.emails_opened == 0:
            return 0.0
        return (self.emails_clicked / self.emails_opened) * 100

    def increment_stat(self, stat_name: str, count: int = 1) -> None:
        """Increment a specific statistic."""
        current_value = getattr(self, stat_name, 0)
        setattr(self, stat_name, current_value + count)
        self.save(update_fields=[stat_name])

    @classmethod
    def get_or_create_today(cls) -> 'NotificationStats':
        """Get or create stats for today."""
        today = timezone.now().date()
        stats, created = cls.objects.get_or_create(date=today)
        return stats

    class Meta:
        db_table = 'notifications_stats'
        verbose_name = 'Notification Stats'
        verbose_name_plural = 'Notification Stats'
        ordering = ['-date']
