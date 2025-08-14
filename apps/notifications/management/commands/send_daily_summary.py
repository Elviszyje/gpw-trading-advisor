"""
Daily Summary Test Command
Creates test data and sends comprehensive daily summaries.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from apps.analysis.models import TradingSignal
from apps.core.models import StockSymbol, TradingSession
from apps.notifications.enhanced_notification_service import get_enhanced_notification_service
from apps.users.models import User
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate and send comprehensive daily summary with test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send summary to',
            required=True
        )
        parser.add_argument(
            '--telegram-chat-id',
            type=str,
            help='Telegram chat ID to send summary to',
            default='7676229144'
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test trading data for the summary'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('📋 Starting Daily Summary Test')
        )
        
        email = options['email']
        chat_id = options['telegram_chat_id']
        create_data = options['create_test_data']
        
        # Run the test
        asyncio.run(self._run_summary_test(email, chat_id, create_data))

    async def _run_summary_test(self, email: str, chat_id: str, create_data: bool):
        """Run daily summary test."""
        
        service = get_enhanced_notification_service()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 DAILY SUMMARY PREPARATION')
        self.stdout.write('='*60)
        
        # Create or get test user
        test_user = await self._setup_test_user(email, chat_id)
        
        if create_data:
            # Create test trading data
            await self._create_test_trading_data()
        
        # Generate summary statistics
        await self._show_summary_preview()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📧 SENDING DAILY SUMMARY')
        self.stdout.write('='*60)
        
        # Send the actual summary
        try:
            success = await service.send_daily_summary(test_user)
            
            if success:
                self.stdout.write(self.style.SUCCESS('✅ Daily summary sent successfully!'))
                self.stdout.write(f'  📧 Email sent to: {email}')
                self.stdout.write(f'  📱 Telegram sent to: {chat_id}')
            else:
                self.stdout.write(self.style.ERROR('❌ Failed to send daily summary'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error sending summary: {e}'))

    async def _setup_test_user(self, email: str, chat_id: str):
        """Create or update test user."""
        from asgiref.sync import sync_to_async
        
        self.stdout.write(f'👤 Setting up test user for {email}...')
        
        # Get or create user
        try:
            user = await sync_to_async(User.objects.get)(email=email)
            self.stdout.write('  ✅ Found existing user')
        except User.DoesNotExist:
            user = await sync_to_async(User.objects.create_user)(
                username=f'test_{email.split("@")[0]}',
                email=email,
                first_name='Test',
                last_name='User',
                password='testpass123'
            )
            self.stdout.write('  ✅ Created new test user')
        
        # Update user settings
        user.email_notifications = True
        user.telegram_chat_id = chat_id
        await sync_to_async(user.save)()
        
        self.stdout.write(f'  📧 Email notifications: Enabled')
        self.stdout.write(f'  📱 Telegram chat ID: {chat_id}')
        
        return user

    async def _create_test_trading_data(self):
        """Create realistic test trading data."""
        from asgiref.sync import sync_to_async
        
        self.stdout.write('📈 Creating test trading data...')
        
        # Get or create today's session
        today = timezone.now().date()
        session, created = await sync_to_async(TradingSession.objects.get_or_create)(
            date=today,
            defaults={'is_active': True}
        )
        
        if created:
            self.stdout.write('  ✅ Created new trading session for today')
        
        # Get some stocks to work with
        stocks = await sync_to_async(list)(
            StockSymbol.objects.filter(is_active=True, is_monitored=True)[:5]
        )
        
        if not stocks:
            self.stdout.write('  ⚠️  No monitored stocks found, creating test stocks...')
            # Create test stocks
            test_stocks = [
                {'symbol': 'PKN', 'name': 'PKN Orlen'},
                {'symbol': 'PZU', 'name': 'PZU'},
                {'symbol': 'LPP', 'name': 'LPP'},
                {'symbol': 'PKNP', 'name': 'PKN Orlen Preferred'},
            ]
            
            for stock_data in test_stocks:
                stock, created = await sync_to_async(StockSymbol.objects.get_or_create)(
                    symbol=stock_data['symbol'],
                    defaults={
                        'name': stock_data['name'],
                        'is_active': True,
                        'is_monitored': True
                    }
                )
                if created:
                    stocks.append(stock)
        
        # Create diverse signals
        signal_types = ['buy', 'sell', 'hold']
        strengths = ['weak', 'moderate', 'strong']
        confidences = [65.5, 72.3, 81.7, 88.2, 93.1]
        
        signals_created = 0
        for i, stock in enumerate(stocks[:4]):  # Use up to 4 stocks
            # Create 2-3 signals per stock
            for j in range(2 + (i % 2)):  # 2 or 3 signals
                signal = await sync_to_async(TradingSignal.objects.create)(
                    stock=stock,
                    trading_session=session,
                    signal_type=signal_types[j % len(signal_types)],
                    strength=strengths[j % len(strengths)],
                    confidence=Decimal(str(confidences[j % len(confidences)])),
                    price_at_signal=Decimal(f'{100 + i * 20 + j * 5}.{j * 25}'),
                    target_price=Decimal(f'{105 + i * 20 + j * 5}.{j * 30}') if signal_types[j % len(signal_types)] == 'buy' else None,
                    stop_loss_price=Decimal(f'{95 + i * 20 + j * 5}.{j * 15}') if signal_types[j % len(signal_types)] in ['buy', 'sell'] else None,
                    generated_by='test_summary_system',
                    is_sent=j % 2 == 0  # Mark some as sent, some as unsent
                )
                signals_created += 1
        
        self.stdout.write(f'  ✅ Created {signals_created} test signals')

    async def _show_summary_preview(self):
        """Show what will be included in the summary."""
        from asgiref.sync import sync_to_async
        
        self.stdout.write('📊 Summary Preview:')
        
        today = timezone.now().date()
        
        # Get today's signals
        today_signals = await sync_to_async(list)(
            TradingSignal.objects.filter(created_at__date=today)
            .select_related('stock')
            .order_by('-created_at')
        )
        
        if not today_signals:
            self.stdout.write('  ⚠️  No signals found for today')
            return
        
        # Group by signal type
        buy_signals = [s for s in today_signals if s.signal_type == 'buy']
        sell_signals = [s for s in today_signals if s.signal_type == 'sell']
        hold_signals = [s for s in today_signals if s.signal_type == 'hold']
        
        self.stdout.write(f'  📈 BUY signals: {len(buy_signals)}')
        for signal in buy_signals[:3]:  # Show first 3
            self.stdout.write(f'    - {signal.stock.symbol}: {signal.confidence}% confidence')
        
        self.stdout.write(f'  📉 SELL signals: {len(sell_signals)}')
        for signal in sell_signals[:3]:
            self.stdout.write(f'    - {signal.stock.symbol}: {signal.confidence}% confidence')
        
        self.stdout.write(f'  📊 HOLD signals: {len(hold_signals)}')
        for signal in hold_signals[:3]:
            self.stdout.write(f'    - {signal.stock.symbol}: {signal.confidence}% confidence')
        
        # Calculate average confidence
        if today_signals:
            avg_confidence = sum(float(s.confidence) for s in today_signals) / len(today_signals)
            self.stdout.write(f'  🎯 Average confidence: {avg_confidence:.1f}%')
        
        # Show top performers
        top_signals = sorted(today_signals, key=lambda x: x.confidence, reverse=True)[:3]
        self.stdout.write('  🏆 Top signals by confidence:')
        for signal in top_signals:
            self.stdout.write(f'    - {signal.stock.symbol}: {signal.signal_type.upper()} ({signal.confidence}%)')
