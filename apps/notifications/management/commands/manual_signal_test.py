"""
Manual signal processing test to verify notification delivery.
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.analysis.models import TradingSignal
from apps.notifications.signal_integration import get_signal_notification_integrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manually process specific signals for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--signal-id',
            type=int,
            help='Process specific signal by ID'
        )
        parser.add_argument(
            '--all-pending',
            action='store_true',
            help='Process all pending signals'
        )
        parser.add_argument(
            '--include-hold',
            action='store_true',
            help='Include HOLD signals in processing'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔄 Manual Signal Processing Test')
        )
        
        # Run the test
        asyncio.run(self._process_signals(options))

    async def _process_signals(self, options):
        """Process signals manually."""
        
        integrator = get_signal_notification_integrator()
        
        if options.get('signal_id'):
            # Process specific signal
            await self._process_specific_signal(options['signal_id'], integrator)
        elif options.get('all_pending'):
            # Process all pending signals
            await self._process_all_pending(integrator, options.get('include_hold', False))
        else:
            # Show available signals
            await self._show_available_signals()

    async def _process_specific_signal(self, signal_id: int, integrator):
        """Process a specific signal."""
        try:
            signal = await sync_to_async(TradingSignal.objects.get)(pk=signal_id)
            
            self.stdout.write(f'📈 Processing signal: {signal.stock.symbol} - {signal.signal_type.upper()}')
            
            stats = await integrator.send_signal_notification(signal)
            
            self.stdout.write(f'📊 Results:')
            self.stdout.write(f'  📧 Email sent: {stats.get("email_sent", 0)}')
            self.stdout.write(f'  📱 Telegram sent: {stats.get("telegram_sent", 0)}')
            self.stdout.write(f'  ❌ Failed: {stats.get("failed", 0)}')
            
            # Check if marked as sent
            await sync_to_async(signal.refresh_from_db)()
            status = '✅ SENT' if signal.is_sent else '⏳ STILL PENDING'
            self.stdout.write(f'  🎯 Status: {status}')
            
        except TradingSignal.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Signal {signal_id} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))

    async def _process_all_pending(self, integrator, include_hold: bool):
        """Process all pending signals."""
        
        # Get pending signals
        signal_types = ['buy', 'sell']
        if include_hold:
            signal_types.append('hold')
        
        pending_signals = await sync_to_async(list)(
            TradingSignal.objects.filter(
                is_sent=False,
                signal_type__in=signal_types,
                created_at__date=timezone.now().date()
            ).select_related('stock').order_by('-created_at')
        )
        
        self.stdout.write(f'📊 Found {len(pending_signals)} pending signals to process')
        
        total_email = 0
        total_telegram = 0
        total_failed = 0
        
        for signal in pending_signals:
            self.stdout.write(f'\n📈 Processing: {signal.stock.symbol} - {signal.signal_type.upper()} ({signal.confidence}%)')
            
            try:
                stats = await integrator.send_signal_notification(signal)
                
                total_email += stats.get('email_sent', 0)
                total_telegram += stats.get('telegram_sent', 0)
                total_failed += stats.get('failed', 0)
                
                self.stdout.write(f'  📧 Email: {stats.get("email_sent", 0)} | 📱 Telegram: {stats.get("telegram_sent", 0)} | ❌ Failed: {stats.get("failed", 0)}')
                
                # Check status
                await sync_to_async(signal.refresh_from_db)()
                status = '✅ SENT' if signal.is_sent else '⏳ PENDING'
                self.stdout.write(f'  🎯 Status: {status}')
                
            except Exception as e:
                total_failed += 1
                self.stdout.write(f'  ❌ Error: {e}')
        
        self.stdout.write(f'\n📊 TOTAL RESULTS:')
        self.stdout.write(f'  📧 Total emails sent: {total_email}')
        self.stdout.write(f'  📱 Total Telegram messages sent: {total_telegram}')
        self.stdout.write(f'  ❌ Total failures: {total_failed}')

    async def _show_available_signals(self):
        """Show available signals for processing."""
        
        today_signals = await sync_to_async(list)(
            TradingSignal.objects.filter(
                created_at__date=timezone.now().date()
            ).select_related('stock').order_by('-created_at')
        )
        
        if not today_signals:
            self.stdout.write('📊 No signals found for today')
            return
        
        self.stdout.write('📈 Available signals for processing:')
        self.stdout.write('='*60)
        
        for signal in today_signals:
            status = '✅ SENT' if signal.is_sent else '⏳ PENDING'
            time_str = signal.created_at.strftime('%H:%M:%S')
            self.stdout.write(
                f'ID: {signal.pk:3} | {time_str} | {signal.stock.symbol:4} | '
                f'{signal.signal_type.upper():4} | {signal.confidence}% | {status}'
            )
        
        self.stdout.write('\nUsage examples:')
        self.stdout.write('  python manage.py manual_signal_test --signal-id=123')
        self.stdout.write('  python manage.py manual_signal_test --all-pending')
        self.stdout.write('  python manage.py manual_signal_test --all-pending --include-hold')
