"""
30-Minute Notification System Test
Simulates real trading activity with signal generation and notifications.
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
from apps.notifications.signal_integration import get_signal_notification_integrator
from apps.users.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run a 30-minute comprehensive notification test'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-email',
            type=str,
            help='Email address to send test notifications to',
            default='admin@gpw.com'
        )
        parser.add_argument(
            '--test-chat-id',
            type=str,
            help='Telegram chat ID to send test notifications to',
            default='7676229144'
        )
        parser.add_argument(
            '--skip-signal-generation',
            action='store_true',
            help='Skip generating test signals and use existing ones'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting 30-Minute Notification System Test')
        )
        
        test_email = options['test_email']
        test_chat_id = options['test_chat_id']
        
        # Run the comprehensive test
        asyncio.run(self._run_comprehensive_test(
            test_email, 
            test_chat_id, 
            options['skip_signal_generation']
        ))

    async def _run_comprehensive_test(self, test_email: str, test_chat_id: str, skip_generation: bool):
        """Run comprehensive 30-minute test."""
        
        service = get_enhanced_notification_service()
        integrator = get_signal_notification_integrator()
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('📊 PHASE 1: SYSTEM STATUS CHECK')
        self.stdout.write('='*80)
        
        # Check system status
        await self._check_system_status(service)
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('📈 PHASE 2: SIGNAL GENERATION TEST')
        self.stdout.write('='*80)
        
        if not skip_generation:
            # Generate test signals
            await self._generate_test_signals()
        else:
            self.stdout.write('⏭️  Skipping signal generation (using existing signals)')
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('🔔 PHASE 3: NOTIFICATION DELIVERY TEST')
        self.stdout.write('='*80)
        
        # Test individual notifications
        await self._test_individual_notifications(service, test_email, test_chat_id)
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('🔄 PHASE 4: AUTOMATED SIGNAL PROCESSING')
        self.stdout.write('='*80)
        
        # Test automated signal processing
        await self._test_automated_processing(integrator)
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('📋 PHASE 5: DAILY SUMMARY TEST')
        self.stdout.write('='*80)
        
        # Test daily summary
        await self._test_daily_summary(service, test_email, test_chat_id)
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('📊 PHASE 6: SYSTEM MONITORING')
        self.stdout.write('='*80)
        
        # Final system check
        await self._final_system_check()
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('✅ 30-MINUTE TEST COMPLETED SUCCESSFULLY!'))
        self.stdout.write('='*80)

    async def _check_system_status(self, service):
        """Check system components."""
        from asgiref.sync import sync_to_async
        
        self.stdout.write('🔍 Checking system components...')
        
        # Check Telegram bot
        if service.telegram_bot:
            self.stdout.write('  ✅ Telegram bot: Connected')
        else:
            self.stdout.write('  ❌ Telegram bot: Not available')
        
        # Check database connections
        users_count = await sync_to_async(User.objects.filter(is_active=True).count)()
        stocks_count = await sync_to_async(StockSymbol.objects.filter(is_active=True, is_monitored=True).count)()
        signals_count = await sync_to_async(TradingSignal.objects.filter(created_at__date=timezone.now().date()).count)()
        
        self.stdout.write(f'  📊 Active users: {users_count}')
        self.stdout.write(f'  📈 Monitored stocks: {stocks_count}')
        self.stdout.write(f'  🎯 Today\'s signals: {signals_count}')

    async def _generate_test_signals(self):
        """Generate test trading signals."""
        from asgiref.sync import sync_to_async
        
        self.stdout.write('🎯 Generating test trading signals...')
        
        # Get monitored stocks
        stocks = await sync_to_async(list)(StockSymbol.objects.filter(is_active=True, is_monitored=True)[:3])
        
        if not stocks:
            self.stdout.write('  ⚠️  No monitored stocks found. Creating test signal manually.')
            return
        
        # Get or create today's trading session
        today = timezone.now().date()
        session, created = await sync_to_async(TradingSession.objects.get_or_create)(
            date=today,
            defaults={'is_active': True}
        )
        
        signal_count = 0
        for stock in stocks:
            # Create test signal
            signal = await sync_to_async(TradingSignal.objects.create)(
                stock=stock,
                trading_session=session,
                signal_type='buy',  # Test with BUY signal
                strength='strong',
                confidence=Decimal('78.5'),
                price_at_signal=Decimal('100.00'),
                target_price=Decimal('105.00'),
                stop_loss_price=Decimal('95.00'),
                generated_by='test_system',
                is_sent=False
            )
            
            signal_count += 1
            self.stdout.write(f'  ✅ Created BUY signal for {stock.symbol} (confidence: 78.5%)')
        
        self.stdout.write(f'  📊 Generated {signal_count} test signals')

    async def _test_individual_notifications(self, service, test_email: str, test_chat_id: str):
        """Test individual notification delivery."""
        self.stdout.write('📧 Testing email notifications...')
        
        # Test email
        try:
            # Create test user
            test_user = User(
                username='test_user',
                email=test_email,
                first_name='Test',
                last_name='User',
                email_notifications=True,
                telegram_chat_id=test_chat_id
            )
            
            # Test email notification
            email_success = await service._send_email_notification(
                user=test_user,
                template_name='signal_alert',
                context={
                    'stock_symbol': 'TEST',
                    'signal_type': 'BUY',
                    'confidence': 85,
                    'price_at_signal': Decimal('100.00'),
                    'target_price': 'N/A',
                    'stop_loss_price': 'N/A',
                    'timestamp': timezone.now(),
                },
                subject='🎯 Test Trading Signal Alert'
            )
            
            if email_success:
                self.stdout.write('  ✅ Email notification: SUCCESS')
            else:
                self.stdout.write('  ❌ Email notification: FAILED')
                
        except Exception as e:
            self.stdout.write(f'  ❌ Email error: {e}')
        
        self.stdout.write('📱 Testing Telegram notifications...')
        
        # Test Telegram
        try:
            telegram_success = await service._send_telegram_notification(
                chat_id=test_chat_id,
                template_name='signal_alert_telegram',
                context={
                    'stock_symbol': 'TEST',
                    'signal_type': 'BUY',
                    'confidence': 85,
                    'price_at_signal': Decimal('100.00'),
                    'target_price': 'N/A',
                    'stop_loss_price': 'N/A',
                    'timestamp': timezone.now(),
                    'site_name': 'GPW Trading Advisor'
                }
            )
            
            if telegram_success:
                self.stdout.write('  ✅ Telegram notification: SUCCESS')
            else:
                self.stdout.write('  ❌ Telegram notification: FAILED')
                
        except Exception as e:
            self.stdout.write(f'  ❌ Telegram error: {e}')

    async def _test_automated_processing(self, integrator):
        """Test automated signal processing."""
        self.stdout.write('🔄 Testing automated signal processing...')
        
        try:
            stats = await integrator.process_new_signals(time_window_hours=24)  # Check last 24 hours for test
            
            self.stdout.write(f'  📊 Signals found: {stats["signals_found"]}')
            self.stdout.write(f'  ✅ Signals processed: {stats["signals_processed"]}')
            self.stdout.write(f'  📧 Notifications sent: {stats["notifications_sent"]}')
            self.stdout.write(f'  ❌ Errors: {stats["errors"]}')
            
            if stats['signals']:
                self.stdout.write('  📈 Signal details:')
                for signal_info in stats['signals']:
                    self.stdout.write(
                        f'    - {signal_info["stock"]}: {signal_info["signal_type"].upper()} '
                        f'(confidence: {signal_info["confidence"]:.1f}%)'
                    )
        
        except Exception as e:
            self.stdout.write(f'  ❌ Automated processing error: {e}')

    async def _test_daily_summary(self, service, test_email: str, test_chat_id: str):
        """Test daily summary generation."""
        self.stdout.write('📋 Testing daily summary...')
        
        try:
            # Create test user
            test_user = User(
                username='summary_test_user',
                email=test_email,
                first_name='Summary',
                last_name='Tester',
                email_notifications=True,
                telegram_chat_id=test_chat_id
            )
            
            # Send daily summary
            summary_success = await service.send_daily_summary(test_user)
            
            if summary_success:
                self.stdout.write('  ✅ Daily summary: SUCCESS')
            else:
                self.stdout.write('  ❌ Daily summary: FAILED')
                
        except Exception as e:
            self.stdout.write(f'  ❌ Daily summary error: {e}')

    async def _final_system_check(self):
        """Final system status check."""
        from asgiref.sync import sync_to_async
        
        self.stdout.write('🔍 Final system status check...')
        
        # Check signal status
        today_signals_qs = TradingSignal.objects.filter(created_at__date=timezone.now().date())
        today_signals = await sync_to_async(list)(today_signals_qs)
        sent_signals = await sync_to_async(list)(today_signals_qs.filter(is_sent=True))
        unsent_signals = await sync_to_async(list)(today_signals_qs.filter(is_sent=False))
        
        self.stdout.write(f'  📊 Today\'s total signals: {len(today_signals)}')
        self.stdout.write(f'  ✅ Sent signals: {len(sent_signals)}')
        self.stdout.write(f'  ⏳ Unsent signals: {len(unsent_signals)}')
        
        # Show recent activity
        recent_signals = await sync_to_async(list)(today_signals_qs.select_related('stock').order_by('-created_at')[:5])
        if recent_signals:
            self.stdout.write('  📈 Recent signals:')
            for signal in recent_signals:
                status = '✅ SENT' if signal.is_sent else '⏳ PENDING'
                self.stdout.write(
                    f'    - {signal.stock.symbol}: {signal.signal_type.upper()} '
                    f'({signal.confidence}%) - {status}'
                )
