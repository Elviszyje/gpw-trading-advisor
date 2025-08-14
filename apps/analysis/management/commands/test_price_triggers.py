"""
Management command to test and demonstrate the Price-Based Trigger Service.
"""

from typing import Optional
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal

from apps.analysis.price_trigger_service import PriceBasedTriggerService, PriceTriggerConfig
from apps.core.models import StockSymbol, TradingSession  
from apps.scrapers.models import StockData, ScrapingSource


class Command(BaseCommand):
    help = 'Test and demonstrate Price-Based Trigger Service functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--profile',
            type=str,
            default='default',
            choices=['aggressive', 'default', 'conservative'],
            help='Trigger sensitivity profile to use'
        )
        parser.add_argument(
            '--stock',
            type=str,
            help='Test specific stock symbol (optional)'
        )
        parser.add_argument(
            '--simulate-data',
            action='store_true',
            help='Create simulation data for testing triggers'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run analysis without generating actual signals'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🎯 Price-Based Trigger Service Test')
        )
        self.stdout.write("=" * 60)
        
        profile = options['profile']
        stock_symbol = options.get('stock')
        simulate_data = options['simulate_data']
        dry_run = options['dry_run']
        
        # Show configuration
        config = PriceTriggerConfig.get_config(profile)
        self.stdout.write(f"\n📊 Using '{profile}' profile:")
        for key, value in config.items():
            self.stdout.write(f"  • {key}: {value}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN MODE - No signals will be generated"))
        
        # Create simulation data if requested
        if simulate_data:
            self.stdout.write(f"\n🧪 Creating simulation data...")
            self._create_simulation_data(stock_symbol)
        
        # Initialize service with profile
        service = PriceBasedTriggerService()
        # Apply profile configuration
        for key, value in config.items():
            if hasattr(service, key):
                setattr(service, key, Decimal(str(value)) if isinstance(value, (int, float)) else value)
        
        # Run trigger analysis
        self.stdout.write(f"\n🔍 Running price trigger analysis...")
        
        if dry_run:
            # Modify service to skip signal generation for dry run
            original_should_generate = service._should_generate_immediate_signal
            service._should_generate_immediate_signal = lambda triggers: False
        
        result = service.check_for_trigger_events()
        
        # Display results
        self._display_results(result, dry_run)
        
        # Show detailed analysis for specific stock if requested
        if stock_symbol:
            self._analyze_specific_stock(service, stock_symbol)
    
    def _create_simulation_data(self, stock_symbol: Optional[str] = None):
        """Create simulation data to test triggers."""
        
        # Get or create stock for simulation
        if stock_symbol:
            try:
                stock = StockSymbol.objects.get(symbol=stock_symbol.upper())
            except StockSymbol.DoesNotExist:
                stock = StockSymbol.objects.create(
                    symbol=stock_symbol.upper(),
                    name=f"Test Stock {stock_symbol.upper()}",
                    is_monitored=True
                )
        else:
            # Use first monitored stock or create one
            stock = StockSymbol.objects.filter(is_monitored=True).first()
            if not stock:
                stock = StockSymbol.objects.create(
                    symbol='TEST',
                    name='Test Stock for Triggers',
                    is_monitored=True
                )
        
        # Get or create current trading session
        current_session, _ = TradingSession.objects.get_or_create(
            date=timezone.now().date(),
            defaults={'status': 'active'}
        )
        
        # Get default source for simulation data
        default_source = ScrapingSource.objects.filter(source_type='stooq').first()
        if not default_source:
            default_source = ScrapingSource.objects.first()
        
        if not default_source:
            self.stdout.write(self.style.ERROR("❌ No scraping source available for simulation"))
            return
        
        current_time = timezone.now()
        base_price = Decimal('100.00')
        base_volume = 50000
        
        # Create data points simulating various trigger scenarios
        simulation_scenarios = [
            # 1. Starting baseline (20 min ago)
            {'price': base_price, 'volume': base_volume, 'minutes_ago': 20},
            
            # 2. Small increase (15 min ago) 
            {'price': base_price * Decimal('1.005'), 'volume': base_volume * 1.1, 'minutes_ago': 15},
            
            # 3. Moderate increase (10 min ago)
            {'price': base_price * Decimal('1.01'), 'volume': base_volume * 1.2, 'minutes_ago': 10},
            
            # 4. Significant price jump with volume spike (5 min ago) - Should trigger
            {'price': base_price * Decimal('1.025'), 'volume': base_volume * 1.6, 'minutes_ago': 5},
            
            # 5. Current price - Major breakout - Should trigger!  
            {'price': base_price * Decimal('1.045'), 'volume': base_volume * 2.3, 'minutes_ago': 0},
        ]
        
        self.stdout.write(f"  📈 Creating simulation data for {stock.symbol}...")
        
        for scenario in simulation_scenarios:
            data_time = current_time - timedelta(minutes=scenario['minutes_ago'])
            
            # Delete existing data at this time to avoid conflicts
            StockData.objects.filter(
                stock=stock,
                data_timestamp=data_time
            ).delete()
            
            StockData.objects.create(
                stock=stock,
                trading_session=current_session,
                source=default_source,
                data_timestamp=data_time,
                open_price=scenario['price'] * Decimal('0.99'),
                high_price=scenario['price'] * Decimal('1.01'),
                low_price=scenario['price'] * Decimal('0.98'),
                close_price=scenario['price'],
                volume=int(scenario['volume'])
            )
        
        self.stdout.write(
            f"  ✅ Created {len(simulation_scenarios)} data points for trigger testing"
        )
    
    def _display_results(self, result: dict, dry_run: bool = False):
        """Display analysis results."""
        
        if result['success']:
            self.stdout.write(f"\n✅ Analysis completed successfully")
            self.stdout.write(f"   📊 Monitored stocks: {result['monitored_stocks']}")
            self.stdout.write(f"   🎯 Trigger events found: {result['trigger_events']}")
            self.stdout.write(f"   ⚡ Priority signals generated: {result['signals_generated']}")
            
            if dry_run and result['trigger_events'] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"   📝 DRY RUN: Would have generated signals for {result['trigger_events']} events"
                    )
                )
            
            # Display detailed trigger events
            if result['events']:
                self.stdout.write(f"\n🔍 DETAILED TRIGGER EVENTS:")
                self.stdout.write("-" * 50)
                
                for i, event in enumerate(result['events'], 1):
                    self.stdout.write(f"\n{i}. {event['stock']} at {event['timestamp'].strftime('%H:%M:%S')}")
                    
                    triggers = event['triggers']
                    
                    if triggers.get('price_change_trigger'):
                        pt = triggers['price_change_trigger']
                        direction_emoji = "📈" if pt['direction'] == 'up' else "📉"
                        self.stdout.write(
                            f"   {direction_emoji} Price Change: {pt['change_percent']:.2f}% "
                            f"({pt['current_price']:.2f} from {pt['previous_price']:.2f})"
                        )
                    
                    if triggers.get('volume_trigger'):
                        vt = triggers['volume_trigger']
                        self.stdout.write(
                            f"   📊 Volume Spike: {vt['volume_ratio']:.2f}x average "
                            f"({vt['current_volume']:,} vs {vt['average_volume']:,})"
                        )
                    
                    if triggers.get('breakout_trigger'):
                        bt = triggers['breakout_trigger']
                        if bt['type'] == 'resistance_breakout':
                            self.stdout.write(
                                f"   🚀 Resistance Breakout: {bt['current_price']:.2f} above {bt['resistance_level']:.2f}"
                            )
                        else:
                            self.stdout.write(
                                f"   📉 Support Breakdown: {bt['current_price']:.2f} below {bt['support_level']:.2f}"
                            )
                    
                    if triggers.get('momentum_trigger'):
                        mt = triggers['momentum_trigger']
                        momentum_emoji = "⚡" if 'up' in mt['direction'] else "🔻"
                        self.stdout.write(
                            f"   {momentum_emoji} Momentum Shift: {mt['momentum_change_percent']:.2f}% "
                            f"({mt['direction'].replace('_', ' ').title()})"
                        )
            else:
                self.stdout.write(f"\n💤 No trigger events detected in current market conditions")
        
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
            )
    
    def _analyze_specific_stock(self, service: PriceBasedTriggerService, stock_symbol: str):
        """Provide detailed analysis for a specific stock."""
        
        try:
            stock = StockSymbol.objects.get(symbol=stock_symbol.upper())
        except StockSymbol.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ Stock {stock_symbol.upper()} not found")
            )
            return
        
        self.stdout.write(f"\n📋 DETAILED ANALYSIS FOR {stock.symbol}")
        self.stdout.write("=" * 50)
        
        # Get recent stock data
        current_time = timezone.now()
        cutoff_time = current_time - timedelta(minutes=int(service.monitoring_window_minutes))
        
        recent_data = StockData.objects.filter(
            stock=stock,
            data_timestamp__gte=cutoff_time
        ).order_by('-data_timestamp')[:20]
        
        if not recent_data.exists():
            self.stdout.write("❌ No recent data available for analysis")
            return
        
        self.stdout.write(f"📊 Recent data points: {recent_data.count()}")
        self.stdout.write(f"⏰ Monitoring window: {service.monitoring_window_minutes} minutes")
        
        # Show recent prices
        self.stdout.write(f"\n💰 Recent Prices:")
        for i, data in enumerate(recent_data[:5]):
            time_str = data.data_timestamp.strftime('%H:%M:%S')
            self.stdout.write(
                f"  {i+1}. {time_str}: {data.close_price:.2f} "
                f"(Volume: {data.volume:,})"
            )
        
        # Analyze triggers for this specific stock
        triggers = service._analyze_stock_triggers(stock, current_time)
        
        if triggers['has_triggers']:
            self.stdout.write(f"\n🎯 ACTIVE TRIGGERS:")
            for trigger_type, trigger_data in triggers.items():
                if trigger_data and trigger_type != 'has_triggers':
                    self.stdout.write(f"  ✅ {trigger_type}: {trigger_data}")
        else:
            self.stdout.write(f"\n💤 No active triggers detected")
        
        # Show configuration thresholds
        self.stdout.write(f"\n⚙️  TRIGGER THRESHOLDS:")
        self.stdout.write(f"  • Price change: ≥{service.price_change_threshold}%")
        self.stdout.write(f"  • Volume spike: ≥{service.volume_spike_threshold}x average")
        self.stdout.write(f"  • Breakout: ≥{service.breakout_threshold}% beyond support/resistance")
