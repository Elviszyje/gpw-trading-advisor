"""
Notification scheduling system using Celery tasks.
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.notifications.enhanced_notification_service import get_enhanced_notification_service
from apps.notifications.preference_manager import NotificationPreferenceManager
from apps.users.models import User
from apps.analysis.models import TradingSignal

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Schedule and manage notification delivery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schedule-daily-summaries',
            action='store_true',
            help='Schedule daily summaries for all users (run at end of trading day)'
        )
        parser.add_argument(
            '--process-signal-queue',
            action='store_true',
            help='Process pending signal alerts (run every 5 minutes)'
        )
        parser.add_argument(
            '--schedule-time',
            type=str,
            default='17:30',
            help='Time to schedule daily summaries (format: HH:MM)'
        )

    def handle(self, *args, **options):
        if options['schedule_daily_summaries']:
            asyncio.run(self._schedule_daily_summaries())
        
        if options['process_signal_queue']:
            asyncio.run(self._process_signal_queue())
        
        if not any([options['schedule_daily_summaries'], options['process_signal_queue']]):
            self.stdout.write('Running all scheduled notification tasks...')
            asyncio.run(self._process_signal_queue())

    async def _schedule_daily_summaries(self):
        """Schedule daily summaries for all eligible users."""
        self.stdout.write('Scheduling daily summaries...')
        
        try:
            service = get_enhanced_notification_service()
            users = NotificationPreferenceManager.get_users_for_broadcast('daily_summary')
            
            today = timezone.now()
            scheduled_count = 0
            
            for user in users:
                try:
                    # Send daily summary
                    success = await service.send_daily_summary(user, today)
                    if success:
                        scheduled_count += 1
                        
                except Exception as e:
                    logger.error(f"Error scheduling daily summary for user {user.pk}: {e}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Daily summaries scheduled for {scheduled_count} users"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error scheduling daily summaries: {e}")
            )

    async def _process_signal_queue(self):
        """Process pending signal alerts."""
        self.stdout.write('Processing signal queue...')
        
        try:
            service = get_enhanced_notification_service()
            
            # Get unsent signals from the last 2 hours
            two_hours_ago = timezone.now() - timedelta(hours=2)
            pending_signals = TradingSignal.objects.filter(
                created_at__gte=two_hours_ago,
                is_sent=False
            ).select_related('stock')
            
            processed_count = 0
            failed_count = 0
            
            for signal in pending_signals:
                try:
                    # Send signal alert
                    stats = await service.send_trading_signal_alert(signal)
                    
                    # Update signal status
                    signal.is_sent = True
                    signal.sent_at = timezone.now()
                    signal.save(update_fields=['is_sent', 'sent_at'])
                    
                    processed_count += 1
                    
                    self.stdout.write(
                        f"Processed signal: {signal.stock.symbol} "
                        f"({signal.signal_type}) - "
                        f"Email: {stats['email_sent']}, "
                        f"Telegram: {stats['telegram_sent']}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing signal {signal.pk}: {e}")
                    failed_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Signal queue processed: {processed_count} sent, {failed_count} failed"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error processing signal queue: {e}")
            )
