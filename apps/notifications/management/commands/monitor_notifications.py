"""
Real-time monitoring script for the notification test.
Shows current system status and recent activity.
"""

import asyncio
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.analysis.models import TradingSignal
from apps.core.models import StockSymbol
from apps.users.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor notification system in real-time'

    def add_arguments(self, parser):
        parser.add_argument(
            '--refresh-seconds',
            type=int,
            default=5,
            help='Refresh interval in seconds'
        )
        parser.add_argument(
            '--max-cycles',
            type=int,
            default=12,  # 1 minute with 5-second intervals
            help='Maximum monitoring cycles'
        )

    def handle(self, *args, **options):
        refresh_seconds = options['refresh_seconds']
        max_cycles = options['max_cycles']
        
        self.stdout.write(
            self.style.SUCCESS(f'🔄 Starting real-time monitoring (refresh every {refresh_seconds}s)')
        )
        
        # Run the monitoring
        asyncio.run(self._monitor_system(refresh_seconds, max_cycles))

    async def _monitor_system(self, refresh_seconds: int, max_cycles: int):
        """Monitor system in real-time."""
        
        for cycle in range(max_cycles):
            # Clear screen and show header
            print('\n' + '='*80)
            print(f'📊 NOTIFICATION SYSTEM MONITOR - Cycle {cycle + 1}/{max_cycles}')
            print(f'⏰ {datetime.now().strftime("%H:%M:%S")}')
            print('='*80)
            
            await self._show_current_status()
            
            if cycle < max_cycles - 1:  # Don't sleep on last cycle
                await asyncio.sleep(refresh_seconds)
        
        print('\n' + '='*80)
        print('✅ MONITORING COMPLETE')
        print('='*80)

    async def _show_current_status(self):
        """Show current system status."""
        
        # Get system statistics
        today = timezone.now().date()
        
        # Total counts
        total_users = await sync_to_async(User.objects.filter(is_active=True).count)()
        total_stocks = await sync_to_async(StockSymbol.objects.filter(is_active=True, is_monitored=True).count)()
        
        # Today's signals
        today_signals_qs = TradingSignal.objects.filter(created_at__date=today)
        today_total = await sync_to_async(today_signals_qs.count)()
        today_sent = await sync_to_async(today_signals_qs.filter(is_sent=True).count)()
        today_unsent = await sync_to_async(today_signals_qs.filter(is_sent=False).count)()
        
        # Show statistics
        print(f'👥 Active Users: {total_users}')
        print(f'📈 Monitored Stocks: {total_stocks}')
        print(f'🎯 Today\'s Signals: {today_total} (✅ Sent: {today_sent}, ⏳ Pending: {today_unsent})')
        
        # Show recent signals
        recent_signals = await sync_to_async(list)(
            today_signals_qs.select_related('stock').order_by('-created_at')[:5]
        )
        
        if recent_signals:
            print('\n📈 Recent Signals:')
            for signal in recent_signals:
                status = '✅ SENT' if signal.is_sent else '⏳ PENDING'
                timestamp = signal.created_at.strftime('%H:%M:%S')
                print(f'  {timestamp} - {signal.stock.symbol}: {signal.signal_type.upper()} ({signal.confidence}%) - {status}')
        else:
            print('\n📈 No signals generated today yet.')
        
        # Show signal breakdown by type
        if today_total > 0:
            buy_signals = await sync_to_async(today_signals_qs.filter(signal_type='buy').count)()
            sell_signals = await sync_to_async(today_signals_qs.filter(signal_type='sell').count)()
            hold_signals = await sync_to_async(today_signals_qs.filter(signal_type='hold').count)()
            
            print(f'\n📊 Signal Breakdown: 📈 BUY: {buy_signals} | 📉 SELL: {sell_signals} | 📊 HOLD: {hold_signals}')
        
        # Show notification-enabled users
        notification_users = await sync_to_async(User.objects.filter(
            is_active=True, 
            email_notifications=True
        ).count)()
        telegram_users = await sync_to_async(User.objects.filter(
            is_active=True, 
            telegram_chat_id__isnull=False
        ).exclude(telegram_chat_id='').count)()
        
        print(f'🔔 Notification Settings: 📧 Email: {notification_users} users | 📱 Telegram: {telegram_users} users')
