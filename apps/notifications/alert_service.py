"""
Real-time Alert System for Trading Signals
Handles instant notifications, email alerts, and push notifications
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q

from apps.notifications.models import Notification, NotificationTemplate, NotificationQueue
from apps.analysis.models import TradingSignal
from apps.users.models import User, NotificationPreferences
from apps.core.models import StockSymbol

import logging
import json

logger = logging.getLogger(__name__)


class TradingAlertService:
    """
    Comprehensive trading alert system.
    Handles real-time notifications for trading signals and market events.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def send_signal_alert(self, signal: TradingSignal, users: Optional[List[User]] = None) -> Dict[str, Any]:
        """
        Send instant alert for new trading signal.
        
        Args:
            signal: TradingSignal instance
            users: Optional list of users to notify (default: all subscribed users)
            
        Returns:
            Dictionary with sending statistics
        """
        self.logger.info(f"Sending signal alert for {signal.stock.symbol} - {signal.signal_type}")
        
        # Get users to notify
        if users is None:
            users = self._get_users_for_signal_alert(signal)
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Check user preferences
                if not self._should_notify_user(user, signal):
                    continue
                
                # Create notification
                notification = self._create_signal_notification(user, signal)
                
                # Queue for delivery
                self._queue_notification(notification)
                
                sent_count += 1
                self.logger.info(f"Queued signal alert for user {user.username}")
                
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error sending alert to user {user.username}: {str(e)}")
        
        return {
            'signal_id': signal.pk,
            'stock_symbol': signal.stock.symbol,
            'signal_type': signal.signal_type,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_users': len(users)
        }
    
    def send_price_alert(self, stock: StockSymbol, current_price: Decimal, trigger_type: str) -> Dict[str, Any]:
        """
        Send price-based alerts (support/resistance breaks, unusual moves, etc.).
        
        Args:
            stock: StockSymbol instance
            current_price: Current stock price
            trigger_type: Type of price alert ('support_break', 'resistance_break', 'unusual_volume', etc.)
            
        Returns:
            Dictionary with sending statistics
        """
        self.logger.info(f"Sending price alert for {stock.symbol}: {trigger_type} at {current_price}")
        
        # Get users with price alerts for this stock
        users = self._get_users_for_price_alert(stock, trigger_type)
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Create price alert notification
                notification = self._create_price_alert_notification(user, stock, current_price, trigger_type)
                
                # Queue for delivery
                self._queue_notification(notification)
                
                sent_count += 1
                self.logger.info(f"Queued price alert for user {user.username}")
                
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error sending price alert to user {user.username}: {str(e)}")
        
        return {
            'stock_symbol': stock.symbol,
            'trigger_type': trigger_type,
            'current_price': float(current_price),
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_users': len(users)
        }
    
    def send_daily_summary(self, user: User) -> bool:
        """
        Send daily trading summary to user.
        
        Args:
            user: User instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get today's signals for user's watchlist
            today = timezone.now().date()
            user_stocks = user.stock_watchlists.values_list('stock', flat=True)
            
            daily_signals = TradingSignal.objects.filter(
                trading_session__date=today,
                stock__in=user_stocks,
                generated_by='daily_trading_system'
            ).select_related('stock', 'trading_session')
            
            if not daily_signals.exists():
                return True  # No signals to send
            
            # Create daily summary notification
            notification = self._create_daily_summary_notification(user, daily_signals)
            
            # Queue for delivery
            self._queue_notification(notification)
            
            self.logger.info(f"Queued daily summary for user {user.username}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending daily summary to user {user.username}: {str(e)}")
            return False
    
    def process_notification_queue(self) -> Dict[str, int]:
        """
        Process pending notifications in the queue.
        
        Returns:
            Dictionary with processing statistics
        """
        self.logger.info("Processing notification queue...")
        
        # Get pending notifications
        pending_notifications = NotificationQueue.objects.filter(
            status='pending',
            scheduled_for__lte=timezone.now()
        ).select_related('notification', 'notification__user')
        
        sent_count = 0
        failed_count = 0
        
        for queue_item in pending_notifications:
            try:
                notification = queue_item.notification
                success = self._deliver_notification(notification)
                
                if success:
                    queue_item.status = 'sent'
                    queue_item.sent_at = timezone.now()
                    notification.status = 'sent'
                    notification.sent_at = timezone.now()
                    sent_count += 1
                else:
                    queue_item.status = 'failed'
                    queue_item.retry_count += 1
                    notification.status = 'failed'
                    notification.retry_count += 1
                    failed_count += 1
                
                queue_item.save()
                notification.save()
                
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error processing notification {queue_item.pk}: {str(e)}")
        
        self.logger.info(f"Processed notifications: {sent_count} sent, {failed_count} failed")
        
        return {
            'processed': pending_notifications.count(),
            'sent': sent_count,
            'failed': failed_count
        }
    
    def _get_users_for_signal_alert(self, signal: TradingSignal) -> List[User]:
        """Get users who should receive signal alerts."""
        # Get users who have this stock in their watchlist and want signal alerts
        return User.objects.filter(
            stock_watchlists__stock=signal.stock,
            notification_preferences__signal_alerts=True,
            is_active=True
        ).distinct()
    
    def _get_users_for_price_alert(self, stock: StockSymbol, trigger_type: str) -> List[User]:
        """Get users who should receive price alerts."""
        return User.objects.filter(
            stock_watchlists__stock=stock,
            notification_preferences__price_alerts=True,
            is_active=True
        ).distinct()
    
    def _should_notify_user(self, user: User, signal: TradingSignal) -> bool:
        """Check if user should be notified about this signal."""
        try:
            prefs = user.notification_preferences
            
            # Check if signal alerts are enabled
            if not prefs.signal_alerts:
                return False
            
            # Check confidence threshold
            if signal.confidence < prefs.min_signal_confidence:
                return False
            
            # Check signal types
            if prefs.signal_types and signal.signal_type not in prefs.signal_types:
                return False
            
            # Check quiet hours
            current_time = timezone.localtime().time()
            if prefs.quiet_hours_start and prefs.quiet_hours_end:
                if prefs.quiet_hours_start <= current_time <= prefs.quiet_hours_end:
                    return False
            
            return True
            
        except NotificationPreferences.DoesNotExist:
            # Default to sending if no preferences set
            return True
        except Exception as e:
            self.logger.error(f"Error checking notification preferences for user {user.username}: {str(e)}")
            return False
    
    def _create_signal_notification(self, user: User, signal: TradingSignal) -> Notification:
        """Create notification for trading signal."""
        # Get notification template
        template = NotificationTemplate.objects.filter(
            template_type='signal_alert',
            is_active=True
        ).first()
        
        if not template:
            # Create default template
            template = self._create_default_signal_template()
        
        # Render content
        context = {
            'user': user,
            'signal': signal,
            'stock': signal.stock,
            'confidence': signal.confidence,
            'signal_type': signal.get_signal_type_display(),
            'price': signal.price_at_signal,
            'target_price': signal.target_price,
            'stop_loss_price': signal.stop_loss_price
        }
        
        subject = template.render_subject(context)
        content = template.render_content(context)
        
        # Determine delivery method
        delivery_method = self._get_user_delivery_method(user)
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            notification_type='signal_alert',
            delivery_method=delivery_method,
            subject=subject,
            content=content,
            related_signal=signal,
            scheduled_at=timezone.now()
        )
        
        return notification
    
    def _create_price_alert_notification(
        self, 
        user: User, 
        stock: StockSymbol, 
        current_price: Decimal, 
        trigger_type: str
    ) -> Notification:
        """Create notification for price alert."""
        # Get notification template
        template = NotificationTemplate.objects.filter(
            template_type='price_alert',
            is_active=True
        ).first()
        
        if not template:
            template = self._create_default_price_alert_template()
        
        # Render content
        context = {
            'user': user,
            'stock': stock,
            'current_price': current_price,
            'trigger_type': trigger_type,
            'timestamp': timezone.now()
        }
        
        subject = template.render_subject(context)
        content = template.render_content(context)
        
        # Determine delivery method
        delivery_method = self._get_user_delivery_method(user)
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            notification_type='price_alert',
            delivery_method=delivery_method,
            subject=subject,
            content=content,
            scheduled_at=timezone.now()
        )
        
        return notification
    
    def _create_daily_summary_notification(self, user: User, signals: List[TradingSignal]) -> Notification:
        """Create daily summary notification."""
        # Get notification template
        template = NotificationTemplate.objects.filter(
            template_type='daily_summary',
            is_active=True
        ).first()
        
        if not template:
            template = self._create_default_daily_summary_template()
        
        # Prepare signals summary
        buy_signals = [s for s in signals if s.signal_type == 'buy']
        sell_signals = [s for s in signals if s.signal_type == 'sell']
        
        context = {
            'user': user,
            'date': timezone.now().date(),
            'total_signals': len(signals),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'signals': signals
        }
        
        subject = template.render_subject(context)
        content = template.render_content(context)
        
        # Daily summaries are typically email
        delivery_method = 'email'
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            notification_type='daily_summary',
            delivery_method=delivery_method,
            subject=subject,
            content=content,
            scheduled_at=timezone.now()
        )
        
        return notification
    
    def _queue_notification(self, notification: Notification):
        """Queue notification for delivery."""
        NotificationQueue.objects.create(
            notification=notification,
            status='pending',
            scheduled_for=notification.scheduled_at,
            priority=self._get_notification_priority(notification)
        )
    
    def _deliver_notification(self, notification: Notification) -> bool:
        """Deliver notification via appropriate channel."""
        try:
            if notification.delivery_method in ['email', 'both']:
                success = self._send_email(notification)
                if not success and notification.delivery_method == 'email':
                    return False
            
            if notification.delivery_method in ['telegram', 'both']:
                success = self._send_telegram(notification)
                if not success and notification.delivery_method == 'telegram':
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error delivering notification {notification.pk}: {str(e)}")
            notification.error_message = str(e)
            notification.save()
            return False
    
    def _send_email(self, notification: Notification) -> bool:
        """Send email notification."""
        try:
            send_mail(
                subject=notification.subject,
                message=notification.content if not notification.is_html else '',
                html_message=notification.content if notification.is_html else None,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.user.email],
                fail_silently=False
            )
            
            self.logger.info(f"Email sent to {notification.user.email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email to {notification.user.email}: {str(e)}")
            return False
    
    def _send_telegram(self, notification: Notification) -> bool:
        """Send Telegram notification."""
        # TODO: Implement Telegram bot integration
        self.logger.info(f"Telegram notification queued for {notification.user.username}")
        return True
    
    def _get_user_delivery_method(self, user: User) -> str:
        """Get preferred delivery method for user."""
        try:
            prefs = user.notification_preferences
            return prefs.delivery_method
        except NotificationPreferences.DoesNotExist:
            return 'email'  # Default to email
    
    def _get_notification_priority(self, notification: Notification) -> int:
        """Get priority for notification."""
        priority_map = {
            'signal_alert': 1,  # High priority
            'price_alert': 2,   # Medium priority
            'daily_summary': 3, # Low priority
            'system_alert': 1,  # High priority
        }
        return priority_map.get(notification.notification_type, 3)
    
    def _create_default_signal_template(self) -> NotificationTemplate:
        """Create default signal alert template."""
        template = NotificationTemplate.objects.create(
            name='Default Signal Alert',
            template_type='signal_alert',
            subject_template='🚨 Trading Signal: {{ signal.signal_type|upper }} {{ stock.symbol }}',
            content_template='''
Hello {{ user.get_full_name|default:user.username }},

A new trading signal has been generated:

📈 Stock: {{ stock.symbol }} ({{ stock.name }})
🎯 Signal: {{ signal_type }}
💪 Confidence: {{ confidence }}%
💰 Current Price: {{ price }}
🎯 Target Price: {{ target_price }}
🛡️ Stop Loss: {{ stop_loss_price }}

Generated at: {{ signal.created_at }}

Best regards,
GPW Trading Advisor
            ''',
            is_html=False,
            is_active=True
        )
        return template
    
    def _create_default_price_alert_template(self) -> NotificationTemplate:
        """Create default price alert template."""
        template = NotificationTemplate.objects.create(
            name='Default Price Alert',
            template_type='price_alert',
            subject_template='💰 Price Alert: {{ stock.symbol }} - {{ trigger_type }}',
            content_template='''
Hello {{ user.get_full_name|default:user.username }},

Price alert triggered for {{ stock.symbol }}:

📊 Current Price: {{ current_price }}
⚡ Trigger: {{ trigger_type }}
⏰ Time: {{ timestamp }}

Best regards,
GPW Trading Advisor
            ''',
            is_html=False,
            is_active=True
        )
        return template
    
    def _create_default_daily_summary_template(self) -> NotificationTemplate:
        """Create default daily summary template."""
        template = NotificationTemplate.objects.create(
            name='Default Daily Summary',
            template_type='daily_summary',
            subject_template='📊 Daily Trading Summary - {{ date }}',
            content_template='''
Hello {{ user.get_full_name|default:user.username }},

Here's your daily trading summary for {{ date }}:

📈 Total Signals: {{ total_signals }}
🟢 Buy Signals: {{ buy_signals|length }}
🔴 Sell Signals: {{ sell_signals|length }}

{% for signal in signals %}
• {{ signal.stock.symbol }}: {{ signal.signal_type|upper }} ({{ signal.confidence }}%)
{% endfor %}

Best regards,
GPW Trading Advisor
            ''',
            is_html=False,
            is_active=True
        )
        return template
