"""
Management command to collect stock data from stooq.pl
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from apps.scrapers.scraping import SimpleStockDataCollector
from apps.core.models import StockSymbol


class Command(BaseCommand):
    help = 'Collect stock data from stooq.pl for monitored stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Specific stock symbol to collect (optional)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Collect data for all monitored stocks',
        )

    def handle(self, *args, **options):
        collector = SimpleStockDataCollector()
        
        if options['symbol']:
            # Collect data for specific symbol
            symbol = options['symbol'].upper()
            self.stdout.write(f"Collecting data for {symbol}...")
            
            success = collector.collect_stock_data(symbol)
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully collected data for {symbol}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to collect data for {symbol}')
                )
                raise SystemExit(1)  # Non-zero exit code for failure
                
        elif options['all']:
            # Collect data for all monitored stocks
            self.stdout.write("Collecting data for all monitored stocks...")
            
            results = collector.collect_all_monitored_stocks()
            
            successful = [symbol for symbol, success in results.items() if success]
            failed = [symbol for symbol, success in results.items() if not success]
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Collection complete:\n'
                    f'  • Successful: {len(successful)} stocks {successful}\n'
                    f'  • Failed: {len(failed)} stocks {failed}'
                )
            )
            
            # Exit with error if ALL stocks failed (complete failure)
            if len(successful) == 0 and len(failed) > 0:
                raise SystemExit(1)  # Non-zero exit code indicates failure
            
        else:
            # Show help and available stocks
            monitored_stocks = StockSymbol.active.filter(is_monitored=True)
            
            self.stdout.write("GPW Stock Data Collector")
            self.stdout.write("Available monitored stocks:")
            for stock in monitored_stocks:
                self.stdout.write(f"  • {stock.symbol} - {stock.name}")
            
            self.stdout.write("\nUsage:")
            self.stdout.write("  python manage.py collect_stock_data --symbol PKN")
            self.stdout.write("  python manage.py collect_stock_data --all")
