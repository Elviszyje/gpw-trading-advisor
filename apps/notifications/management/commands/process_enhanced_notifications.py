"""
Enhanced notification processing management command.
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal
from asgiref.sync import sync_to_async

from apps.notifications.enhanced_notification_service import get_enhanced_notification_service
from apps.notifications.preference_manager import NotificationPreferenceManager
from apps.notifications.signal_integration import get_signal_notification_integrator
from apps.users.models import User
from apps.analysis.models import TradingSignal
from apps.scrapers.models import StockData

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process enhanced notifications and alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-signal-alerts',
            action='store_true',
            help='Send alerts for new trading signals from the last hour'
        )
        parser.add_argument(
            '--send-daily-summaries',
            action='store_true',
            help='Send daily summaries to all eligible users'
        )
        parser.add_argument(
            '--send-price-alerts',
            action='store_true',
            help='Check and send price alerts'
        )
        parser.add_argument(
            '--test-email',
            type=str,
            help='Send test notification to specific email address'
        )
        parser.add_argument(
            '--test-telegram',
            type=str,
            help='Send test notification to specific Telegram chat ID'
        )
        parser.add_argument(
            '--check-preferences',
            action='store_true',
            help='Check and display notification preferences for all users'
        )
        parser.add_argument(
            '--auto-process-signals',
            action='store_true',
            help='Automatically process and send notifications for new trading signals'
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting enhanced notification processing...')
        
        service = get_enhanced_notification_service()
        
        if options['send_signal_alerts']:
            asyncio.run(self._send_signal_alerts(service))
        
        if options['send_daily_summaries']:
            asyncio.run(self._send_daily_summaries(service))
        
        if options['send_price_alerts']:
            asyncio.run(self._send_price_alerts(service))
        
        if options['test_email']:
            asyncio.run(self._test_email_notification(service, options['test_email']))
        
        if options['test_telegram']:
            asyncio.run(self._test_telegram_notification(service, options['test_telegram']))
        
        if options['check_preferences']:
            self._check_user_preferences()
        
        if options['auto_process_signals']:
            asyncio.run(self._auto_process_signals())
        
        if not any([
            options['send_signal_alerts'],
            options['send_daily_summaries'], 
            options['send_price_alerts'],
            options['test_email'],
            options['test_telegram'],
            options['check_preferences']
        ]):
            self.stdout.write(
                self.style.WARNING('No action specified. Use --help to see available options.')
            )

    async def _send_signal_alerts(self, service):
        """Send alerts for new trading signals."""
        self.stdout.write('Checking for new trading signals...')
        
        try:
            # Use sync_to_async for Django ORM calls
            @sync_to_async
            def get_new_signals():
                one_hour_ago = timezone.now() - timedelta(hours=1)
                return list(TradingSignal.objects.filter(
                    created_at__gte=one_hour_ago,
                    is_sent=False
                ).select_related('stock'))
            
            @sync_to_async
            def mark_signal_sent(signal):
                signal.is_sent = True
                signal.sent_at = timezone.now()
                signal.save(update_fields=['is_sent', 'sent_at'])
            
            new_signals = await get_new_signals()
            
            total_sent = 0
            total_failed = 0
            
            for signal in new_signals:
                try:
                    stats = await service.send_trading_signal_alert(signal)
                    
                    # Mark signal as sent
                    await mark_signal_sent(signal)
                    
                    total_sent += stats['email_sent'] + stats['telegram_sent']
                    total_failed += stats['failed']
                    
                    self.stdout.write(
                        f"Signal {signal.stock.symbol} ({signal.signal_type}): "
                        f"Email: {stats['email_sent']}, Telegram: {stats['telegram_sent']}, "
                        f"Failed: {stats['failed']}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error sending signal alert for {signal.pk}: {e}")
                    total_failed += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Signal alerts completed. Sent: {total_sent}, Failed: {total_failed}"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error in signal alert processing: {e}")
            )

    async def _send_daily_summaries(self, service):
        """Send daily summaries to eligible users."""
        self.stdout.write('Sending daily summaries...')
        
        try:
            users = NotificationPreferenceManager.get_users_for_broadcast('daily_summary')
            
            total_sent = 0
            total_failed = 0
            
            for user in users:
                try:
                    success = await service.send_daily_summary(user)
                    if success:
                        total_sent += 1
                        self.stdout.write(f"Daily summary sent to {user.email}")
                    else:
                        total_failed += 1
                        self.stdout.write(f"Failed to send daily summary to {user.email}")
                        
                except Exception as e:
                    logger.error(f"Error sending daily summary to user {user.pk}: {e}")
                    total_failed += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Daily summaries completed. Sent: {total_sent}, Failed: {total_failed}"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error in daily summary processing: {e}")
            )

    async def _send_price_alerts(self, service):
        """Check and send price alerts."""
        self.stdout.write('Checking for price alerts...')
        
        try:
            # This is a simplified version - you would implement actual price monitoring
            # For now, we'll simulate a price alert
            
            users = User.objects.filter(
                is_active=True,
                email_notifications=True
            )[:5]  # Test with first 5 users
            
            total_sent = 0
            
            for user in users:
                try:
                    # Simulate a price alert for CDR stock
                    success = await service.send_price_alert(
                        user=user,
                        stock_symbol='CDR',
                        alert_type='price_above',
                        current_price=Decimal('125.50'),
                        threshold=Decimal('120.00')
                    )
                    
                    if success:
                        total_sent += 1
                        self.stdout.write(f"Price alert sent to {user.email}")
                    
                except Exception as e:
                    logger.error(f"Error sending price alert to user {user.pk}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(f"Price alerts completed. Sent: {total_sent}")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error in price alert processing: {e}")
            )

    async def _test_email_notification(self, service, email):
        """Send test email notification."""
        self.stdout.write(f'Sending test email to {email}...')
        
        try:
            user = await sync_to_async(User.objects.filter(email=email).first)()
            if not user:
                # Create a temporary user for testing
                user = User(
                    username='test_user',
                    email=email,
                    first_name='Test',
                    last_name='User',
                    email_notifications=True
                )
            
            # Test with a mock signal
            from apps.core.models import StockSymbol
            test_stock = await sync_to_async(StockSymbol.objects.first)()
            
            if test_stock:
                success = await service._send_email_notification(
                    user=user,
                    template_name='signal_alert',
                    context={
                        'stock_symbol': test_stock.symbol,
                        'signal_type': 'BUY',
                        'confidence': 85,
                        'price_at_signal': Decimal('100.00'),
                        'target_price': 'N/A',
                        'stop_loss_price': 'N/A',
                        'timestamp': timezone.now(),
                    },
                    subject='🎯 Test Trading Signal Alert'
                )
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f"Test email sent successfully to {email}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to send test email to {email}")
                    )
            else:
                self.stdout.write(
                    self.style.ERROR("No stock symbols available for testing")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error sending test email: {e}")
            )

    async def _test_telegram_notification(self, service, chat_id):
        """Send test Telegram notification."""
        self.stdout.write(f'Sending test Telegram message to {chat_id}...')
        
        try:
            from apps.core.models import StockSymbol
            
            # Use sync_to_async for Django ORM calls
            @sync_to_async
            def get_test_stock():
                return StockSymbol.objects.first()
            
            test_stock = await get_test_stock()
            
            if test_stock:
                success = await service._send_telegram_notification(
                    chat_id=chat_id,
                    template_name='signal_alert_telegram',
                    context={
                        'stock_symbol': test_stock.symbol,
                        'signal_type': 'BUY',
                        'confidence': 85,
                        'price_at_signal': Decimal('100.00'),
                        'target_price': 'N/A',
                        'stop_loss_price': 'N/A',
                        'timestamp': timezone.now(),
                        'site_name': 'GPW Trading Advisor'
                    }
                )
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f"Test Telegram message sent to {chat_id}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to send test Telegram message to {chat_id}")
                    )
            else:
                self.stdout.write(
                    self.style.ERROR("No stock symbols available for testing")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error sending test Telegram message: {e}")
            )

    async def _auto_process_signals(self):
        """Automatically process and send notifications for new trading signals."""
        self.stdout.write('Auto-processing new trading signals...')
        
        try:
            integrator = get_signal_notification_integrator()
            stats = await integrator.process_new_signals(time_window_hours=1)
            
            self.stdout.write(
                f"Found {stats['signals_found']} new signals, "
                f"processed {stats['signals_processed']}, "
                f"sent {stats['notifications_sent']} notifications"
            )
            
            if stats['signals']:
                self.stdout.write('\nSignal Details:')
                for signal_info in stats['signals']:
                    self.stdout.write(
                        f"  - {signal_info['stock']}: {signal_info['signal_type'].upper()} "
                        f"(confidence: {signal_info['confidence']:.1f}%) - "
                        f"Email: {signal_info['notifications'].get('email_sent', 0)}, "
                        f"Telegram: {signal_info['notifications'].get('telegram_sent', 0)}"
                    )
            
            if stats['errors'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"Encountered {stats['errors']} errors during processing")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Auto-processing completed successfully")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error in auto-processing signals: {e}")
            )

    def _check_user_preferences(self):
        """Check and display user notification preferences."""
        self.stdout.write('Checking user notification preferences...')
        
        try:
            users = User.objects.filter(is_active=True)
            
            total_users = users.count()
            email_enabled = users.filter(email_notifications=True).count()
            telegram_enabled = users.exclude(telegram_chat_id__isnull=True).exclude(telegram_chat_id='').count()
            
            self.stdout.write(f"\n📊 Notification Preferences Summary:")
            self.stdout.write(f"Total active users: {total_users}")
            self.stdout.write(f"Email notifications enabled: {email_enabled}")
            self.stdout.write(f"Telegram notifications enabled: {telegram_enabled}")
            
            # Show detailed preferences for first 10 users
            self.stdout.write(f"\n👥 User Details (first 10):")
            for user in users[:10]:
                summary = NotificationPreferenceManager.get_preference_summary(user)
                self.stdout.write(
                    f"  {user.username} ({user.email}): "
                    f"Channels: {summary['enabled_channels']} | "
                    f"Can receive signals: {summary['can_receive_signals']}"
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error checking preferences: {e}")
            )
