"""
Management command for calculating technical indicators.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import StockSymbol, TradingSession
from apps.analysis.models import TechnicalIndicator
from apps.analysis.technical_indicators import IndicatorCalculationService
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate technical indicators for monitored stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Calculate indicators for specific stock symbol (e.g., PKN)',
        )
        
        parser.add_argument(
            '--indicator',
            type=str,
            choices=['rsi', 'sma', 'ema', 'macd', 'bollinger'],
            help='Calculate specific indicator type only',
        )
        
        parser.add_argument(
            '--all-monitored',
            action='store_true',
            help='Calculate indicators for all monitored stocks',
        )
        
        parser.add_argument(
            '--create-defaults',
            action='store_true',
            help='Create default technical indicator configurations',
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be calculated without making changes',
        )

    def handle(self, *args, **options):
        try:
            if options['create_defaults']:
                self.create_default_indicators()
                return

            # Setup calculation service
            calculation_service = IndicatorCalculationService()
            
            # Determine which stocks to process
            stocks = self.get_stocks_to_process(options)
            
            if not stocks:
                self.stdout.write(
                    self.style.WARNING('No stocks found to process')
                )
                return
            
            # Determine which indicators to calculate
            indicator_types = None
            if options['indicator']:
                indicator_types = [options['indicator']]
            
            total_calculated = 0
            
            for stock in stocks:
                self.stdout.write(f"\n=== Processing {stock.symbol} ===")
                
                if options['dry_run']:
                    self.show_dry_run_info(stock, indicator_types)
                    continue
                
                try:
                    with transaction.atomic():
                        results = calculation_service.calculate_indicators_for_stock(
                            stock=stock,
                            indicators=indicator_types
                        )
                        
                        for indicator_type, count in results.items():
                            self.stdout.write(
                                f"  {indicator_type.upper()}: {count} values calculated"
                            )
                            total_calculated += count
                            
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing {stock.symbol}: {str(e)}")
                    )
                    logger.error(f"Error calculating indicators for {stock.symbol}: {str(e)}")
            
            if not options['dry_run']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✅ Successfully calculated {total_calculated} indicator values"
                    )
                )
                
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')

    def get_stocks_to_process(self, options) -> List[StockSymbol]:
        """Get list of stocks to process based on options."""
        if options['symbol']:
            try:
                stock = StockSymbol.objects.get(
                    symbol=options['symbol'].upper(),
                    is_active=True
                )
                return [stock]
            except StockSymbol.DoesNotExist:
                raise CommandError(f"Stock symbol '{options['symbol']}' not found or not active")
        
        elif options['all_monitored']:
            return list(StockSymbol.objects.filter(
                is_monitored=True,
                is_active=True
            ))
        
        else:
            # Default: all monitored stocks
            return list(StockSymbol.objects.filter(
                is_monitored=True,
                is_active=True
            ))

    def show_dry_run_info(self, stock: StockSymbol, indicator_types: Optional[List[str]]):
        """Show what would be calculated in dry run mode."""
        from apps.scrapers.models import StockData
        
        data_count = StockData.objects.filter(stock=stock, is_active=True).count()
        self.stdout.write(f"  Available data points: {data_count}")
        
        if indicator_types:
            indicators = TechnicalIndicator.objects.filter(
                indicator_type__in=indicator_types,
                is_enabled=True
            )
        else:
            indicators = TechnicalIndicator.objects.filter(is_enabled=True)
        
        for indicator in indicators:
            self.stdout.write(f"  Would calculate: {indicator.name} ({indicator.indicator_type})")

    def create_default_indicators(self):
        """Create default technical indicator configurations."""
        defaults = [
            {
                'name': 'RSI (14-period)',
                'indicator_type': 'rsi',
                'description': 'Relative Strength Index with 14-period calculation',
                'parameters': {'period': 14},
                'overbought_threshold': 70.0,
                'oversold_threshold': 30.0,
                'calculation_order': 10,
            },
            {
                'name': 'SMA (20-period)',
                'indicator_type': 'sma',
                'description': 'Simple Moving Average with 20-period calculation',
                'parameters': {'period': 20},
                'calculation_order': 20,
            },
            {
                'name': 'SMA (50-period)',
                'indicator_type': 'sma',
                'description': 'Simple Moving Average with 50-period calculation',
                'parameters': {'period': 50},
                'calculation_order': 21,
            },
            {
                'name': 'EMA (12-period)',
                'indicator_type': 'ema',
                'description': 'Exponential Moving Average with 12-period calculation',
                'parameters': {'period': 12},
                'calculation_order': 30,
            },
            {
                'name': 'EMA (26-period)',
                'indicator_type': 'ema',
                'description': 'Exponential Moving Average with 26-period calculation',
                'parameters': {'period': 26},
                'calculation_order': 31,
            },
            {
                'name': 'MACD (12,26,9)',
                'indicator_type': 'macd',
                'description': 'MACD with standard 12/26/9 periods',
                'parameters': {
                    'fast_period': 12,
                    'slow_period': 26,
                    'signal_period': 9
                },
                'calculation_order': 40,
            },
            {
                'name': 'Bollinger Bands (20,2)',
                'indicator_type': 'bollinger',
                'description': 'Bollinger Bands with 20-period SMA and 2 standard deviations',
                'parameters': {
                    'period': 20,
                    'std_dev': 2.0
                },
                'calculation_order': 50,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for indicator_data in defaults:
            indicator, created = TechnicalIndicator.objects.update_or_create(
                name=indicator_data['name'],
                defaults=indicator_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"✅ Created: {indicator.name}")
            else:
                updated_count += 1
                self.stdout.write(f"🔄 Updated: {indicator.name}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Default indicators setup complete: "
                f"{created_count} created, {updated_count} updated"
            )
        )
