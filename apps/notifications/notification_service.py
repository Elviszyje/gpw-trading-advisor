"""
Enhanced notification service with email and Telegram integration.

This module provides comprehensive notification capabilities including:
- Email notifications with HTML/text templates
- Telegram bot integration for instant messaging
- User preference management
- Notification scheduling and queue processing
- Template-based message formatting
"""

import asyncio
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
from decimal import Decimal
import json

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode

from apps.users.models import User, NotificationPreferences
from apps.notifications.models import (
    Notification, NotificationQueue, NotificationTemplate, 
    NotificationStats
)
from apps.analysis.models import TradingSignal, StockData

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Comprehensive notification service supporting email and Telegram.
    
    Features:
    - Multi-channel delivery (email, Telegram)
    - Template-based message formatting
    - User preference management
    - Queue processing and scheduling
    - Delivery tracking and statistics
    """
    
    def __init__(self):
        self.telegram_bot = None
        self.email_connection = None
        self._initialize_telegram()
    
    def _initialize_telegram(self) -> None:
        """Initialize Telegram bot if token is configured."""
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if telegram_token:
            try:
                self.telegram_bot = Bot(token=telegram_token)
                logger.info("Telegram bot initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                self.telegram_bot = None
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not configured")
    
    async def send_trading_signal_alert(
        self, 
        signal: TradingSignal, 
        users: Optional[List[User]] = None
    ) -> Dict[str, int]:
        """
        Send trading signal alerts to users via their preferred channels.
        
        Args:
            signal: TradingSignal instance
            users: List of users to notify (if None, uses all active users)
            
        Returns:
            Dict with delivery statistics
        """
        if users is None:
            users = list(User.objects.filter(
                is_active=True,
                notificationpreferences__signal_alerts=True
            ).select_related('notificationpreferences'))
        
        stats = {'email_sent': 0, 'telegram_sent': 0, 'failed': 0}
        
        # Prepare signal data for templates
        signal_data = self._prepare_signal_data(signal)
        
        for user in users:
            try:
                prefs = getattr(user, 'notificationpreferences', None)
                if not prefs or not prefs.signal_alerts:
                    continue
                
                # Send email notification
                if prefs.email_notifications:
                    success = await self._send_email_notification(
                        user=user,
                        template_name='signal_alert',
                        context=signal_data,
                        subject=f"🎯 Trading Signal: {signal.stock.symbol} - {signal.signal_type}"
                    )
                    if success:
                        stats['email_sent'] += 1
                    else:
                        stats['failed'] += 1
                
                # Send Telegram notification
                if prefs.telegram_notifications and user.telegram_chat_id:
                    success = await self._send_telegram_notification(
                        chat_id=user.telegram_chat_id,
                        template_name='signal_alert_telegram',
                        context=signal_data
                    )
                    if success:
                        stats['telegram_sent'] += 1
                    else:
                        stats['failed'] += 1
                
                # Log notification
                await self._log_notification(
                    user=user,
                    notification_type='signal_alert',
                    content=f"Trading signal for {signal.stock.symbol}",
                    channels_used=[ch for ch in ['email' if prefs.email_notifications else '',
                                               'telegram' if prefs.telegram_notifications else ''] if ch]
                )
                
            except Exception as e:
                logger.error(f"Failed to send signal alert to user {user.pk}: {e}")
                stats['failed'] += 1
        
        logger.info(f"Signal alert sent: {stats}")
        return stats
    
    async def send_daily_summary(self, user: User, date: Optional[datetime] = None) -> bool:
        """
        Send daily trading summary to a user.
        
        Args:
            user: User to send summary to
            date: Date for summary (defaults to today)
            
        Returns:
            True if sent successfully
        """
        if date is None:
            date = timezone.now().date()
        
        try:
            # Get user preferences
            prefs = getattr(user, 'notificationpreferences', None)
            if not prefs or not prefs.daily_summaries:
                return False
            
            # Prepare summary data
            summary_data = await self._prepare_daily_summary_data(user, date)
            
            success = False
            
            # Send email summary
            if prefs.email_notifications:
                success = await self._send_email_notification(
                    user=user,
                    template_name='daily_summary',
                    context=summary_data,
                    subject=f"📊 Daily Trading Summary - {date.strftime('%Y-%m-%d')}"
                ) or success
            
                # Send Telegram summary
                if prefs.telegram_notifications and user.telegram_chat_id:
                    success = await self._send_telegram_notification(
                        chat_id=user.telegram_chat_id,
                        template_name='daily_summary_telegram',
                        context=summary_data
                    ) or success
                
                if success:
                    await self._log_notification(
                        user=user,
                        notification_type='daily_summary',
                        content=f"Daily summary for {date}",
                        channels_used=[ch for ch in ['email' if prefs.email_notifications else '',
                                                   'telegram' if prefs.telegram_notifications else ''] if ch]
                    )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send daily summary to user {user.id}: {e}")
            return False
    
    async def send_price_alert(
        self, 
        user: User, 
        stock_data: StockData, 
        alert_type: str, 
        threshold: Decimal
    ) -> bool:
        """
        Send price alert notification.
        
        Args:
            user: User to notify
            stock_data: Stock that triggered the alert
            alert_type: Type of alert ('price_above', 'price_below', 'volume_spike')
            threshold: Threshold value that was crossed
            
        Returns:
            True if sent successfully
        """
        try:
            prefs = getattr(user, 'notificationpreferences', None)
            if not prefs or not prefs.price_alerts:
                return False
            
            # Prepare alert data
            alert_data = {
                'user': user,
                'stock': stock_data,
                'alert_type': alert_type,
                'threshold': threshold,
                'current_price': stock_data.close_price,
                'current_volume': stock_data.volume,
                'timestamp': timezone.now(),
                'change_percent': stock_data.change_percent,
            }
            
            success = False
            
            # Send email alert
            if prefs.email_notifications:
                success = await self._send_email_notification(
                    user=user,
                    template_name='price_alert',
                    context=alert_data,
                    subject=f"🚨 Price Alert: {stock_data.symbol} - {alert_type.replace('_', ' ').title()}"
                ) or success
            
            # Send Telegram alert
            if prefs.telegram_notifications and user.profile.telegram_chat_id:
                success = await self._send_telegram_notification(
                    chat_id=user.profile.telegram_chat_id,
                    template_name='price_alert_telegram',
                    context=alert_data
                ) or success
            
            if success:
                await self._log_notification(
                    user=user,
                    notification_type='price_alert',
                    content=f"Price alert for {stock_data.symbol}: {alert_type}",
                    channels_used=['email' if prefs.email_notifications else None,
                                 'telegram' if prefs.telegram_notifications else None]
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send price alert to user {user.id}: {e}")
            return False
    
    async def _send_email_notification(
        self, 
        user: User, 
        template_name: str, 
        context: Dict[str, Any], 
        subject: str
    ) -> bool:
        """Send email notification using Django templates."""
        try:
            # Add user to context
            context['user'] = user
            context['site_name'] = getattr(settings, 'SITE_NAME', 'GPW Trading Advisor')
            
            # Render templates
            text_content = render_to_string(
                f'notifications/email/{template_name}.txt',
                context
            )
            html_content = render_to_string(
                f'notifications/email/{template_name}.html',
                context
            )
            
            # Create and send email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                headers={
                    'Message-ID': f"<{timezone.now().timestamp()}@{getattr(settings, 'SITE_DOMAIN', 'localhost')}>",
                    'X-Notification-Type': template_name
                }
            )
            msg.attach_alternative(html_content, "text/html")
            
            # Send email
            result = msg.send(fail_silently=False)
            
            if result:
                logger.info(f"Email sent successfully to {user.email}: {template_name}")
                return True
            else:
                logger.error(f"Failed to send email to {user.email}: {template_name}")
                return False
                
        except Exception as e:
            logger.error(f"Email sending error for user {user.id}: {e}")
            return False
    
    async def _send_telegram_notification(
        self, 
        chat_id: str, 
        template_name: str, 
        context: Dict[str, Any]
    ) -> bool:
        """Send Telegram notification using bot."""
        if not self.telegram_bot:
            logger.warning("Telegram bot not available")
            return False
        
        try:
            # Render Telegram message template
            message = render_to_string(
                f'notifications/telegram/{template_name}.txt',
                context
            )
            
            # Send message
            await self.telegram_bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
            
            logger.info(f"Telegram message sent to {chat_id}: {template_name}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram sending error to {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram to {chat_id}: {e}")
            return False
    
    def _prepare_signal_data(self, signal: TradingSignal) -> Dict[str, Any]:
        """Prepare trading signal data for templates."""
        stock_data = signal.stock_data
        
        return {
            'signal': signal,
            'stock': stock_data,
            'symbol': stock_data.symbol,
            'signal_type': signal.signal_type,
            'confidence': signal.confidence,
            'entry_price': signal.entry_price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'position_size': signal.position_size,
            'current_price': stock_data.close_price,
            'change_percent': stock_data.change_percent,
            'volume': stock_data.volume,
            'timestamp': signal.created_at,
            'indicators': {
                'rsi': getattr(signal, 'rsi_value', None),
                'macd': getattr(signal, 'macd_value', None),
                'bb_position': getattr(signal, 'bb_position', None),
            }
        }
    
    async def _prepare_daily_summary_data(self, user: User, date: datetime.date) -> Dict[str, Any]:
        """Prepare daily summary data for templates."""
        # Get signals for the date
        signals = TradingSignal.objects.filter(
            created_at__date=date
        ).select_related('stock_data').order_by('-confidence')
        
        # Get performance data (if available)
        portfolio_value = 0  # TODO: Calculate from user's portfolio
        daily_pnl = 0  # TODO: Calculate daily P&L
        
        # Market statistics
        total_signals = signals.count()
        buy_signals = signals.filter(signal_type='BUY').count()
        sell_signals = signals.filter(signal_type='SELL').count()
        
        return {
            'user': user,
            'date': date,
            'signals': list(signals[:10]),  # Top 10 signals
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'portfolio_value': portfolio_value,
            'daily_pnl': daily_pnl,
            'market_status': 'Open' if self._is_market_open() else 'Closed',
        }
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open (simplified)."""
        now = timezone.now()
        # Simple check for weekdays during market hours (9:00-17:30 Warsaw time)
        if now.weekday() >= 5:  # Weekend
            return False
        warsaw_time = now.astimezone(timezone.get_current_timezone())
        return 9 <= warsaw_time.hour < 17 or (warsaw_time.hour == 17 and warsaw_time.minute < 30)
    
    async def _log_notification(
        self, 
        user: User, 
        notification_type: str, 
        content: str, 
        channels_used: List[str]
    ) -> None:
        """Log notification to database."""
        try:
            with transaction.atomic():
                notification = await asyncio.to_thread(
                    Notification.objects.create,
                    user=user,
                    notification_type=notification_type,
                    message=content,
                    channels_used=','.join(filter(None, channels_used)),
                    sent_at=timezone.now(),
                    status='sent'
                )
                
                # Update statistics
                await asyncio.to_thread(
                    NotificationStats.objects.update_or_create,
                    user=user,
                    date=timezone.now().date(),
                    defaults={
                        'email_sent': 1 if 'email' in channels_used else 0,
                        'telegram_sent': 1 if 'telegram' in channels_used else 0,
                        'total_sent': 1
                    }
                )
                
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    async def process_notification_queue(self) -> Dict[str, int]:
        """Process pending notifications in the queue."""
        stats = {'processed': 0, 'failed': 0}
        
        try:
            # Get pending notifications
            pending = NotificationQueue.objects.filter(
                status='pending',
                scheduled_for__lte=timezone.now()
            ).select_related('user').order_by('scheduled_for')[:100]
            
            for queue_item in pending:
                try:
                    # Update status to processing
                    queue_item.status = 'processing'
                    queue_item.save()
                    
                    # Process based on notification type
                    success = False
                    if queue_item.notification_type == 'signal_alert':
                        # TODO: Implement queued signal alerts
                        success = True
                    elif queue_item.notification_type == 'daily_summary':
                        success = await self.send_daily_summary(queue_item.user)
                    elif queue_item.notification_type == 'price_alert':
                        # TODO: Implement queued price alerts
                        success = True
                    
                    # Update status
                    if success:
                        queue_item.status = 'sent'
                        queue_item.sent_at = timezone.now()
                        stats['processed'] += 1
                    else:
                        queue_item.status = 'failed'
                        queue_item.attempts += 1
                        stats['failed'] += 1
                    
                    queue_item.save()
                    
                except Exception as e:
                    logger.error(f"Failed to process queue item {queue_item.id}: {e}")
                    queue_item.status = 'failed'
                    queue_item.attempts += 1
                    queue_item.save()
                    stats['failed'] += 1
            
            logger.info(f"Queue processing completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Queue processing error: {e}")
            return stats


# Global service instance
notification_service = NotificationService()


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    return notification_service
