"""
Django management command for importing historical stock data from TXT files.

Usage:
    python manage.py import_historical_data file1.txt file2.txt file3.txt
    python manage.py import_historical_data /path/to/data/*.txt
    python manage.py import_historical_data --directory /path/to/data/
    
File format:
    <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
    08N,5,20250224,110000,0.925,0.925,0.925,0.925,3,0
    
Where PER can be:
    5 - 5-minute intervals
    60 - 1-hour intervals  
    D - daily data
"""

import os
import csv
import glob
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional, Tuple
import pytz

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import StockSymbol, TradingSession, Market
from apps.scrapers.models import ScrapingSource, StockData


class Command(BaseCommand):
    help = 'Import historical stock data from TXT files'

    def add_arguments(self, parser):
        parser.add_argument(
            'files',
            nargs='*',
            type=str,
            help='TXT files to import'
        )
        parser.add_argument(
            '--directory',
            type=str,
            help='Directory containing TXT files to import'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            default=True,
            help='Skip records that already exist (default: True)'
        )
        parser.add_argument(
            '--create-symbols',
            action='store_true',
            default=True,
            help='Create stock symbols if they don\'t exist (default: True)'
        )

    def handle(self, *args, **options):
        files = options['files'] or []
        directory = options['directory']
        dry_run = options['dry_run']
        
        # Collect files to process
        files_to_process = []
        
        if directory:
            if not os.path.isdir(directory):
                raise CommandError(f"Directory does not exist: {directory}")
            
            txt_files = glob.glob(os.path.join(directory, "*.txt"))
            files_to_process.extend(txt_files)
            
        files_to_process.extend(files)
        
        if not files_to_process:
            raise CommandError("No files specified. Use files as arguments or --directory option.")
        
        # Validate files exist
        for file_path in files_to_process:
            if not os.path.isfile(file_path):
                raise CommandError(f"File does not exist: {file_path}")
        
        self.stdout.write(
            self.style.SUCCESS(f"Found {len(files_to_process)} files to process")
        )
        
        # Get or create source for historical imports
        source, created = ScrapingSource.objects.get_or_create(
            name='historical_import',
            defaults={
                'source_type': 'other',
                'base_url': 'file://local',
                'is_enabled': True
            }
        )
        if created:
            self.stdout.write(f"Created new source: {source.name}")
        
        # Process each file
        total_processed = 0
        total_created = 0
        total_updated = 0
        total_skipped = 0
        total_errors = 0
        
        for file_path in files_to_process:
            self.stdout.write(f"\nProcessing: {file_path}")
            
            try:
                stats = self.process_file(
                    file_path, 
                    source, 
                    dry_run, 
                    options['skip_duplicates'],
                    options['create_symbols']
                )
                
                total_processed += stats['processed']
                total_created += stats['created']
                total_updated += stats['updated']
                total_skipped += stats['skipped']
                total_errors += stats['errors']
                
                self.stdout.write(
                    f"  Processed: {stats['processed']}, "
                    f"Created: {stats['created']}, "
                    f"Updated: {stats['updated']}, "
                    f"Skipped: {stats['skipped']}, "
                    f"Errors: {stats['errors']}"
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to process {file_path}: {e}")
                )
                total_errors += 1
        
        # Final summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("IMPORT SUMMARY"))
        self.stdout.write(f"Files processed: {len(files_to_process)}")
        self.stdout.write(f"Total records processed: {total_processed}")
        self.stdout.write(f"Records created: {total_created}")
        self.stdout.write(f"Records updated: {total_updated}")
        self.stdout.write(f"Records skipped: {total_skipped}")
        self.stdout.write(f"Errors: {total_errors}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No data was actually imported"))

    def process_file(
        self, 
        file_path: str, 
        source: ScrapingSource, 
        dry_run: bool,
        skip_duplicates: bool,
        create_symbols: bool
    ) -> Dict[str, int]:
        """Process a single TXT file and return statistics."""
        
        # Extract symbol from filename
        filename = os.path.basename(file_path)
        # Remove test_data_ prefix if present and .txt extension
        symbol = filename.replace('test_data_', '').replace('.txt', '').upper()
        
        return self.process_file_with_symbol(
            file_path, source, symbol, dry_run, skip_duplicates, create_symbols
        )
    
    def process_file_with_symbol(
        self, 
        file_path: str, 
        source: ScrapingSource, 
        symbol: str,
        dry_run: bool,
        skip_duplicates: bool,
        create_symbols: bool
    ) -> Dict[str, int]:
        """Process a single TXT file with explicit symbol and return statistics."""
        
        # Get or create stock symbol
        stock_symbol = None
        try:
            stock_symbol = StockSymbol.objects.get(symbol=symbol)
        except StockSymbol.DoesNotExist:
            if create_symbols:
                if not dry_run:
                    stock_symbol = StockSymbol.objects.create(
                        symbol=symbol,
                        name=f"Auto-imported {symbol}",
                        market=None,  # Will be set manually later
                        is_active=True,
                        is_monitored=False  # Don't auto-monitor imported symbols
                    )
                    self.stdout.write(f"  Created new symbol: {symbol}")
                else:
                    self.stdout.write(f"  Would create new symbol: {symbol}")
            else:
                raise CommandError(f"Symbol {symbol} does not exist and --create-symbols is disabled")
        
        # Parse file and import data
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        with open(file_path, 'r', encoding='utf-8') as file:
            # Skip header if it exists
            first_line = file.readline().strip()
            if first_line.startswith('<TICKER>') or first_line.startswith('TICKER'):
                pass  # Header line, continue to data
            else:
                file.seek(0)  # Reset to beginning if no header
            
            csv_reader = csv.reader(file)
            
            for line_num, row in enumerate(csv_reader, 1):
                try:
                    if len(row) < 10:
                        continue  # Skip incomplete rows
                    
                    # Parse row data
                    ticker = row[0].strip()
                    per = row[1].strip()
                    date_str = row[2].strip()
                    time_str = row[3].strip()
                    open_price = self.parse_decimal(row[4])
                    high_price = self.parse_decimal(row[5])
                    low_price = self.parse_decimal(row[6])
                    close_price = self.parse_decimal(row[7])
                    volume = self.parse_int(row[8])
                    # row[9] is OPENINT (not used)
                    
                    # Validate ticker matches filename
                    if ticker.upper() != symbol:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Line {line_num}: Ticker mismatch {ticker} != {symbol}"
                            )
                        )
                    
                    # Parse timestamp
                    timestamp = self.parse_timestamp(date_str, time_str, per)
                    if not timestamp:
                        stats['errors'] += 1
                        continue
                    
                    # Get or create trading session
                    trading_session = None
                    if not dry_run and stock_symbol:
                        trading_session, _ = TradingSession.objects.get_or_create(
                            date=timestamp.date(),
                            defaults={'is_trading_day': True}
                        )
                    
                    # Check for duplicates
                    if skip_duplicates and stock_symbol:
                        existing = StockData.objects.filter(
                            stock=stock_symbol,
                            data_timestamp=timestamp,
                            source=source
                        ).exists()
                        
                        if existing:
                            stats['skipped'] += 1
                            continue
                    
                    # Calculate price changes
                    price_change = None
                    price_change_percent = None
                    if close_price and open_price and open_price != 0:
                        price_change = close_price - open_price
                        price_change_percent = (price_change / open_price) * Decimal('100')
                    
                    # Create or update record
                    if not dry_run and stock_symbol:
                        with transaction.atomic():
                            stock_data, created = StockData.objects.update_or_create(
                                stock=stock_symbol,
                                data_timestamp=timestamp,
                                source=source,
                                defaults={
                                    'trading_session': trading_session,
                                    'open_price': open_price,
                                    'high_price': high_price,
                                    'low_price': low_price,
                                    'close_price': close_price,
                                    'volume': volume,
                                    'price_change': price_change,
                                    'price_change_percent': price_change_percent,
                                    'raw_data': {
                                        'ticker': ticker,
                                        'per': per,
                                        'import_source': 'historical_txt',
                                        'import_file': os.path.basename(file_path),
                                        'import_line': line_num
                                    }
                                }
                            )
                            
                            if created:
                                stats['created'] += 1
                            else:
                                stats['updated'] += 1
                    else:
                        stats['created'] += 1  # For dry run counting
                    
                    stats['processed'] += 1
                    
                    # Progress indicator
                    if stats['processed'] % 1000 == 0:
                        self.stdout.write(f"  Processed {stats['processed']} records...")
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Line {line_num}: Error processing row: {e}")
                    )
                    stats['errors'] += 1
        
        return stats

    def parse_decimal(self, value: str) -> Optional[Decimal]:
        """Parse decimal value from string."""
        if not value or value.strip() == '':
            return None
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None

    def parse_int(self, value: str) -> Optional[int]:
        """Parse integer value from string."""
        if not value or value.strip() == '':
            return None
        try:
            return int(float(value.strip()))  # Handle decimal notation
        except (ValueError, TypeError):
            return None

    def parse_timestamp(self, date_str: str, time_str: str, per: str) -> Optional[datetime]:
        """Parse timestamp from date and time strings."""
        try:
            # Parse date: YYYYMMDD
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            
            # Parse time: HHMMSS
            if len(time_str) >= 6:
                hour = int(time_str[:2])
                minute = int(time_str[2:4])
                second = int(time_str[4:6])
            else:
                hour = minute = second = 0
            
            # Create datetime
            dt = datetime(year, month, day, hour, minute, second)
            
            # Localize to Warsaw timezone (GPW trading hours)
            warsaw_tz = pytz.timezone('Europe/Warsaw')
            warsaw_dt = warsaw_tz.localize(dt)
            
            return warsaw_dt
            
        except (ValueError, IndexError) as e:
            self.stderr.write(f"Error parsing timestamp {date_str} {time_str}: {e}")
            return None
