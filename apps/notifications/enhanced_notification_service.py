"""
Enhanced notification service with email and Telegram integration.
Simplified version that works with the actual model structure.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async

from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode

from apps.users.models import User
from apps.notifications.models import Notification, NotificationQueue
from apps.analysis.models import TradingSignal
from apps.scrapers.models import StockData

logger = logging.getLogger(__name__)


class EnhancedNotificationService:
    """
    Enhanced notification service supporting email and Telegram.
    Simplified version that works with actual model structure.
    """
    
    def __init__(self):
        self.telegram_bot = None
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
        """Send trading signal alerts to users."""
        if users is None:
            # Get users who want signal alerts using sync_to_async
            users = await sync_to_async(list)(User.objects.filter(
                is_active=True,
                email_notifications=True  # Using direct field from User model
            ))
        
        stats = {'email_sent': 0, 'telegram_sent': 0, 'failed': 0}
        
        # Prepare signal data
        signal_data = {
            'signal': signal,
            'stock_symbol': signal.stock.symbol,
            'signal_type': signal.signal_type,
            'confidence': signal.confidence,
            'price_at_signal': signal.price_at_signal,
            'target_price': signal.target_price or 'N/A',
            'stop_loss_price': signal.stop_loss_price or 'N/A',
            'timestamp': signal.created_at,
        }
        
        for user in users:
            try:
                # Send email notification
                if user.email_notifications:
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
                if user.telegram_chat_id:
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
                    channels_used=['email', 'telegram']
                )
                
            except Exception as e:
                logger.error(f"Failed to send signal alert to user {user.pk}: {e}")
                stats['failed'] += 1
        
        logger.info(f"Signal alert sent: {stats}")
        return stats
    
    async def send_daily_summary(self, user: User, date: Optional[datetime] = None) -> bool:
        """Send daily trading summary to a user."""
        if date is None:
            current_date = timezone.now().date()
        else:
            current_date = date.date() if isinstance(date, datetime) else date
        
        try:
            if not user.email_notifications:
                return False
            
            # Prepare summary data
            summary_data = await self._prepare_daily_summary_data(user, current_date)
            
            success = False
            
            # Send email summary
            if user.email_notifications:
                success = await self._send_email_notification(
                    user=user,
                    template_name='daily_summary',
                    context=summary_data,
                    subject=f"📊 Daily Trading Summary - {current_date.strftime('%Y-%m-%d')}"
                )
            
            # Send Telegram summary
            if user.telegram_chat_id:
                telegram_success = await self._send_telegram_notification(
                    chat_id=user.telegram_chat_id,
                    template_name='daily_summary_telegram',
                    context=summary_data
                )
                success = success or telegram_success
            
            if success:
                await self._log_notification(
                    user=user,
                    notification_type='daily_summary',
                    content=f"Daily summary for {date}",
                    channels_used=['email', 'telegram']
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send daily summary to user {user.pk}: {e}")
            return False
    
    async def send_price_alert(
        self, 
        user: User, 
        stock_symbol: str, 
        alert_type: str, 
        current_price: Decimal,
        threshold: Decimal
    ) -> bool:
        """Send price alert notification."""
        try:
            if not user.email_notifications:
                return False
            
            # Prepare alert data
            alert_data = {
                'user': user,
                'stock_symbol': stock_symbol,
                'alert_type': alert_type,
                'threshold': threshold,
                'current_price': current_price,
                'timestamp': timezone.now(),
            }
            
            success = False
            
            # Send email alert
            if user.email_notifications:
                success = await self._send_email_notification(
                    user=user,
                    template_name='price_alert',
                    context=alert_data,
                    subject=f"🚨 Price Alert: {stock_symbol} - {alert_type.replace('_', ' ').title()}"
                )
            
            # Send Telegram alert
            if user.telegram_chat_id:
                telegram_success = await self._send_telegram_notification(
                    chat_id=user.telegram_chat_id,
                    template_name='price_alert_telegram',
                    context=alert_data
                )
                success = success or telegram_success
            
            if success:
                await self._log_notification(
                    user=user,
                    notification_type='price_alert',
                    content=f"Price alert for {stock_symbol}: {alert_type}",
                    channels_used=['email', 'telegram']
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send price alert to user {user.pk}: {e}")
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
            
            # Render templates using sync_to_async
            text_content = await sync_to_async(render_to_string)(
                f'notifications/email/{template_name}.txt',
                context
            )
            html_content = await sync_to_async(render_to_string)(
                f'notifications/email/{template_name}.html',
                context
            )
            
            # Create email message
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
            
            # Send email using sync_to_async
            result = await sync_to_async(msg.send)(fail_silently=False)
            
            if result:
                logger.info(f"Email sent successfully to {user.email}: {template_name}")
                return True
            else:
                logger.error(f"Failed to send email to {user.email}: {template_name}")
                return False
                
        except Exception as e:
            logger.error(f"Email sending error for user {user.pk}: {e}")
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
            # Render Telegram message template using sync_to_async
            message = await sync_to_async(render_to_string)(
                f'notifications/telegram/{template_name}.txt',
                context
            )
            
            # Send message
            await self.telegram_bot.send_message(
                chat_id=chat_id,
                text=message,
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
    
    async def _prepare_daily_summary_data(self, user: User, target_date: date) -> Dict[str, Any]:
        """Prepare daily summary data for templates."""
        # Get signals for the date using sync_to_async
        signals_queryset = TradingSignal.objects.filter(
            created_at__date=target_date
        ).select_related('stock').order_by('-confidence')
        
        signals = await sync_to_async(list)(signals_queryset)
        
        # Market statistics
        total_signals = len(signals)
        buy_signals = len([s for s in signals if s.signal_type == 'buy'])
        sell_signals = len([s for s in signals if s.signal_type == 'sell'])
        
        return {
            'user': user,
            'date': target_date,
            'signals': signals[:10],  # Top 10 signals
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
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
                    channels_used=','.join(channels_used),
                    sent_at=timezone.now(),
                    status='sent'
                )
                
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")


# Global service instance
enhanced_notification_service = EnhancedNotificationService()


def get_enhanced_notification_service() -> EnhancedNotificationService:
    """Get the global enhanced notification service instance."""
    return enhanced_notification_service
