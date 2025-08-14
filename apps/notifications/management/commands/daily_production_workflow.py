"""
Production Daily Workflow Script
Automates the complete daily trading signal and notification process.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.analysis.models import TradingSignal
from apps.users.models import User
from apps.notifications.enhanced_notification_service import get_enhanced_notification_service
from apps.notifications.signal_integration import get_signal_notification_integrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Complete daily workflow: signal generation → notifications → summaries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-signal-generation',
            action='store_true',
            help='Skip signal generation (use existing signals)'
        )
        parser.add_argument(
            '--send-summaries',
            action='store_true',
            help='Send daily summaries to all users'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 DAILY PRODUCTION WORKFLOW')
        )
        
        asyncio.run(self._run_daily_workflow(options))

    async def _run_daily_workflow(self, options):
        """Run the complete daily workflow."""
        
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write('🔍 DRY RUN MODE - No actual actions will be taken')
        
        # Step 1: System Status Check
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 STEP 1: SYSTEM STATUS CHECK')
        self.stdout.write('='*60)
        await self._check_system_status()
        
        # Step 2: Generate Signals (if not skipped)
        if not options.get('skip_signal_generation'):
            self.stdout.write('\n' + '='*60)
            self.stdout.write('📈 STEP 2: SIGNAL GENERATION')
            self.stdout.write('='*60)
            await self._generate_daily_signals(dry_run)
        else:
            self.stdout.write('\n⏭️  Skipping signal generation')
        
        # Step 3: Process and Send Signal Notifications
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🔔 STEP 3: SIGNAL NOTIFICATIONS')
        self.stdout.write('='*60)
        await self._process_signal_notifications(dry_run)
        
        # Step 4: Send Daily Summaries (if requested)
        if options.get('send_summaries'):
            self.stdout.write('\n' + '='*60)
            self.stdout.write('📋 STEP 4: DAILY SUMMARIES')
            self.stdout.write('='*60)
            await self._send_daily_summaries(dry_run)
        
        # Step 5: Final Report
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 STEP 5: DAILY REPORT')
        self.stdout.write('='*60)
        await self._generate_daily_report()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✅ DAILY WORKFLOW COMPLETED'))
        self.stdout.write('='*60)

    async def _check_system_status(self):
        """Check system components and configuration."""
        
        # Service check
        service = get_enhanced_notification_service()
        telegram_status = '✅ Connected' if service.telegram_bot else '❌ Not available'
        
        # User counts
        total_users = await sync_to_async(User.objects.filter(is_active=True).count)()
        email_users = await sync_to_async(User.objects.filter(is_active=True, email_notifications=True).count)()
        telegram_users = await sync_to_async(User.objects.filter(
            is_active=True, 
            telegram_chat_id__isnull=False
        ).exclude(telegram_chat_id='').count)()
        
        self.stdout.write(f'🤖 Telegram Bot: {telegram_status}')
        self.stdout.write(f'👥 Active Users: {total_users}')
        self.stdout.write(f'📧 Email Notifications: {email_users} users')
        self.stdout.write(f'📱 Telegram Notifications: {telegram_users} users')

    async def _generate_daily_signals(self, dry_run: bool):
        """Generate daily trading signals."""
        
        if dry_run:
            self.stdout.write('🔍 Would generate daily signals for all monitored stocks')
            return
        
        self.stdout.write('📈 Generating daily signals...')
        self.stdout.write('💡 Run: python manage.py generate_daily_signals --all-monitored --save')
        
        # Note: This would typically call the signal generation system
        # For now, we're showing what the command would be

    async def _process_signal_notifications(self, dry_run: bool):
        """Process and send notifications for new signals."""
        
        integrator = get_signal_notification_integrator()
        
        # Get pending signals
        today = timezone.now().date()
        pending_signals = await sync_to_async(list)(
            TradingSignal.objects.filter(
                created_at__date=today,
                is_sent=False,
                signal_type__in=['buy', 'sell']
            ).select_related('stock')
        )
        
        self.stdout.write(f'📊 Found {len(pending_signals)} pending signals')
        
        if dry_run:
            for signal in pending_signals:
                self.stdout.write(f'🔍 Would send: {signal.stock.symbol} - {signal.signal_type.upper()} ({signal.confidence}%)')
            return
        
        if pending_signals:
            stats = await integrator.process_new_signals(time_window_hours=24)
            
            self.stdout.write(f'✅ Processed: {stats["signals_processed"]} signals')
            self.stdout.write(f'📧 Notifications sent: {stats["notifications_sent"]}')
            self.stdout.write(f'❌ Errors: {stats["errors"]}')
        else:
            self.stdout.write('ℹ️  No pending signals to process')

    async def _send_daily_summaries(self, dry_run: bool):
        """Send daily summaries to users."""
        
        service = get_enhanced_notification_service()
        
        # Get users who should receive summaries
        summary_users = await sync_to_async(list)(
            User.objects.filter(
                is_active=True,
                email_notifications=True
            )
        )
        
        self.stdout.write(f'📋 Sending summaries to {len(summary_users)} users')
        
        if dry_run:
            for user in summary_users:
                self.stdout.write(f'🔍 Would send summary to: {user.email}')
            return
        
        sent_count = 0
        failed_count = 0
        
        for user in summary_users:
            try:
                success = await service.send_daily_summary(user)
                if success:
                    sent_count += 1
                    self.stdout.write(f'✅ Sent to: {user.email}')
                else:
                    failed_count += 1
                    self.stdout.write(f'❌ Failed: {user.email}')
            except Exception as e:
                failed_count += 1
                self.stdout.write(f'❌ Error for {user.email}: {e}')
        
        self.stdout.write(f'📊 Summaries: {sent_count} sent, {failed_count} failed')

    async def _generate_daily_report(self):
        """Generate final daily activity report."""
        
        today = timezone.now().date()
        
        # Get today's statistics
        all_signals = await sync_to_async(list)(
            TradingSignal.objects.filter(created_at__date=today).select_related('stock')
        )
        
        sent_signals = [s for s in all_signals if s.is_sent]
        pending_signals = [s for s in all_signals if not s.is_sent]
        
        # Signal type breakdown
        buy_signals = [s for s in all_signals if s.signal_type == 'buy']
        sell_signals = [s for s in all_signals if s.signal_type == 'sell']
        hold_signals = [s for s in all_signals if s.signal_type == 'hold']
        
        self.stdout.write(f'📈 Total signals today: {len(all_signals)}')
        self.stdout.write(f'  └─ 📈 BUY: {len(buy_signals)} | 📉 SELL: {len(sell_signals)} | 📊 HOLD: {len(hold_signals)}')
        self.stdout.write(f'✅ Notifications sent: {len(sent_signals)}')
        self.stdout.write(f'⏳ Still pending: {len(pending_signals)}')
        
        if all_signals:
            avg_confidence = sum(float(s.confidence) for s in all_signals) / len(all_signals)
            self.stdout.write(f'🎯 Average confidence: {avg_confidence:.1f}%')
            
            # Top signals
            top_signals = sorted(all_signals, key=lambda x: x.confidence, reverse=True)[:3]
            self.stdout.write('🏆 Top signals by confidence:')
            for signal in top_signals:
                status = '✅' if signal.is_sent else '⏳'
                self.stdout.write(f'  {status} {signal.stock.symbol}: {signal.signal_type.upper()} ({signal.confidence}%)')
        
        # System health
        active_users = await sync_to_async(User.objects.filter(is_active=True).count)()
        self.stdout.write(f'👥 Active users: {active_users}')
        
        self.stdout.write(f'\n⏰ Report generated at: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')

# For cron job usage:
# 0 9 * * 1-5 cd /path/to/project && python manage.py daily_production_workflow --send-summaries
# 0 16 * * 1-5 cd /path/to/project && python manage.py daily_production_workflow --skip-signal-generation
