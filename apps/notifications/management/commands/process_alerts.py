"""
Management command for processing trading alerts and notifications.
Handles signal alerts, price alerts, and daily summaries.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from apps.notifications.alert_service import TradingAlertService
from apps.analysis.models import TradingSignal
from apps.users.models import User


class Command(BaseCommand):
    help = 'Process trading alerts and notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--process-queue',
            action='store_true',
            help='Process pending notifications in queue'
        )
        
        parser.add_argument(
            '--send-daily-summaries',
            action='store_true',
            help='Send daily summaries to all users'
        )
        
        parser.add_argument(
            '--alert-new-signals',
            action='store_true',
            help='Send alerts for new signals from last hour'
        )
        
        parser.add_argument(
            '--test-notification',
            type=str,
            help='Send test notification to specific username'
        )

    def handle(self, *args, **options):
        """Execute the notification processing command."""
        self.stdout.write(
            self.style.SUCCESS('🔔 Starting Trading Alert Processing...')
        )
        
        alert_service = TradingAlertService()
        
        # Process notification queue
        if options['process_queue']:
            self._process_queue(alert_service)
        
        # Send daily summaries
        if options['send_daily_summaries']:
            self._send_daily_summaries(alert_service)
        
        # Alert for new signals
        if options['alert_new_signals']:
            self._alert_new_signals(alert_service)
        
        # Send test notification
        if options['test_notification']:
            self._send_test_notification(alert_service, options['test_notification'])
        
        # If no specific action, process queue
        if not any([
            options['process_queue'], 
            options['send_daily_summaries'], 
            options['alert_new_signals'],
            options['test_notification']
        ]):
            self._process_queue(alert_service)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Trading Alert Processing Complete!')
        )

    def _process_queue(self, alert_service: TradingAlertService):
        """Process pending notifications."""
        self.stdout.write('📬 Processing notification queue...')
        
        try:
            results = alert_service.process_notification_queue()
            
            self.stdout.write(
                f"✅ Processed {results['processed']} notifications"
            )
            self.stdout.write(
                f"📧 Sent: {results['sent']}"
            )
            self.stdout.write(
                f"❌ Failed: {results['failed']}"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error processing queue: {str(e)}")
            )

    def _send_daily_summaries(self, alert_service: TradingAlertService):
        """Send daily summaries to all active users."""
        self.stdout.write('📊 Sending daily summaries...')
        
        try:
            # Get users who want daily summaries
            users = User.objects.filter(
                is_active=True,
                notification_preferences__daily_summary=True
            )
            
            sent_count = 0
            failed_count = 0
            
            for user in users:
                try:
                    success = alert_service.send_daily_summary(user)
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(f"Error sending summary to {user.username}: {str(e)}")
            
            self.stdout.write(
                f"✅ Daily summaries: {sent_count} sent, {failed_count} failed"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error sending daily summaries: {str(e)}")
            )

    def _alert_new_signals(self, alert_service: TradingAlertService):
        """Send alerts for new signals from the last hour."""
        self.stdout.write('🚨 Checking for new signals to alert...')
        
        try:
            # Get signals from last hour
            cutoff_time = timezone.now() - timedelta(hours=1)
            new_signals = TradingSignal.objects.filter(
                created_at__gte=cutoff_time,
                generated_by='daily_trading_system'
            ).select_related('stock', 'trading_session')
            
            if not new_signals.exists():
                self.stdout.write('📭 No new signals found')
                return
            
            total_sent = 0
            total_failed = 0
            
            for signal in new_signals:
                try:
                    results = alert_service.send_signal_alert(signal)
                    total_sent += results['sent_count']
                    total_failed += results['failed_count']
                    
                    self.stdout.write(
                        f"🎯 {signal.stock.symbol} {signal.signal_type}: "
                        f"{results['sent_count']} alerts sent"
                    )
                    
                except Exception as e:
                    total_failed += 1
                    self.stdout.write(f"Error alerting signal {signal.pk}: {str(e)}")
            
            self.stdout.write(
                f"✅ Signal alerts: {total_sent} sent, {total_failed} failed"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error processing new signals: {str(e)}")
            )

    def _send_test_notification(self, alert_service: TradingAlertService, username: str):
        """Send test notification to specific user."""
        self.stdout.write(f'🧪 Sending test notification to {username}...')
        
        try:
            user = User.objects.get(username=username)
            
            # Get latest signal for testing
            latest_signal = TradingSignal.objects.filter(
                generated_by='daily_trading_system'
            ).select_related('stock', 'trading_session').first()
            
            if not latest_signal:
                self.stdout.write('❌ No signals found for testing')
                return
            
            results = alert_service.send_signal_alert(latest_signal, [user])
            
            self.stdout.write(
                f"✅ Test notification sent: {results['sent_count']} successful, {results['failed_count']} failed"
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ User '{username}' not found")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error sending test notification: {str(e)}")
            )
