"""
Complete workflow: Generate signals and send notifications.
This command handles the full pipeline from data analysis to notification delivery.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.analysis.models import TradingSignal
from apps.core.models import StockSymbol
from apps.users.models import User
from apps.notifications.enhanced_notification_service import get_enhanced_notification_service
import asyncio
from asgiref.sync import sync_to_async
from decimal import Decimal
from datetime import date
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate trading signals and send notifications immediately'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-generate',
            action='store_true',
            help='Force generate test signals if no real signals available',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually sending notifications',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Complete Signal Generation & Notification Workflow')
        )
        
        asyncio.run(self._run_workflow(options))

    async def _run_workflow(self, options):
        """Run the complete workflow."""
        dry_run = options.get('dry_run', False)
        force_generate = options.get('force_generate', False)
        
        # Step 1: Check for recent signals
        today = date.today()
        today_signals = await sync_to_async(list)(
            TradingSignal.objects.filter(
                created_at__date=today,
                signal_type__in=['buy', 'sell']
            ).exclude(is_sent=True).select_related('stock')
        )
        
        self.stdout.write(f"\n📊 Found {len(today_signals)} unsent actionable signals today")
        
        # Step 2: Generate test signals if needed
        if not today_signals and force_generate:
            self.stdout.write("\n🧪 Generating test signals...")
            today_signals = await self._generate_test_signals()
        
        if not today_signals:
            self.stdout.write(
                self.style.WARNING("\n⚠️  No actionable signals to send. Use --force-generate to create test signals.")
            )
            return
        
        # Step 3: Get users to notify
        users = await sync_to_async(list)(
            User.objects.filter(is_active=True)
        )
        
        if not users:
            self.stdout.write(self.style.ERROR("❌ No active users found"))
            return
            
        self.stdout.write(f"\n👥 Will notify {len(users)} active users")
        
        # Step 4: Set up notification service
        notification_service = get_enhanced_notification_service()
        
        # Step 5: Send notifications
        total_sent = 0
        for signal in today_signals:
            self.stdout.write(f"\n📤 Processing signal: {signal.stock.symbol} {signal.signal_type.upper()}")
            
            if dry_run:
                self.stdout.write("   🔍 DRY RUN - Would send notification")
                continue
                
            try:
                stats = await notification_service.send_trading_signal_alert(signal)
                total_sent += stats.get('telegram_sent', 0) + stats.get('email_sent', 0)
                
                # Mark signal as sent
                signal.is_sent = True
                signal.sent_at = timezone.now()
                await sync_to_async(signal.save)()
                
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Sent: {stats}")
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error: {e}")
                )
        
        self.stdout.write(f"\n🎉 Workflow complete! Total notifications sent: {total_sent}")

    async def _generate_test_signals(self):
        """Generate test signals for demonstration."""
        signals = []
        
        # Get some popular stocks
        stocks = await sync_to_async(list)(
            StockSymbol.objects.filter(
                symbol__in=['PKO', 'PKN', 'CDR'],
                is_active=True
            )[:2]
        )
        
        if not stocks:
            return signals
            
        # Get or create trading session
        today = date.today()
        trading_session = await sync_to_async(
            lambda: __import__('apps.core.models', fromlist=['TradingSession']).TradingSession.objects.get_or_create(
                date=today,
                defaults={'is_open': True}
            )[0]
        )()
        
        for i, stock in enumerate(stocks):
            signal_type = 'buy' if i % 2 == 0 else 'sell'
            price = Decimal('25.50') + (i * Decimal('5.00'))
            
            signal = await sync_to_async(TradingSignal.objects.create)(
                stock=stock,
                trading_session=trading_session,
                signal_type=signal_type,
                strength='strong',
                confidence=Decimal('78.5') + (i * 2),
                price_at_signal=price,
                target_price=price * Decimal('1.08') if signal_type == 'buy' else price * Decimal('0.92'),
                stop_loss_price=price * Decimal('0.95') if signal_type == 'buy' else price * Decimal('1.05'),
                analysis_details={'test': True, 'generated_for': 'notification_test'},
                generated_by='test_generator',
                is_automatic=False,
                notes=f'Test {signal_type} signal for notification verification'
            )
            
            # Refresh with stock relation
            signal = await sync_to_async(
                TradingSignal.objects.select_related('stock').get
            )(pk=signal.pk)
            
            signals.append(signal)
            self.stdout.write(f"   ✅ Created {signal.stock.symbol} {signal_type.upper()} signal")
        
        return signals
