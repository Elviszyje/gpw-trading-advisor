"""
Web scraping utilities for GPW Trading Advisor.
Handles data extraction from stooq.pl using CSV export endpoint.

This module provides:
- StooqCSVScraper: CSV-based scraper for reliable data extraction
- SimpleStockDataCollector: High-level interface for stock data collection

The CSV approach is more reliable than browser automation and provides
accurate OHLCV data with proper timezone handling (Warsaw -> UTC).
"""

import requests
import csv
import time
from io import StringIO
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional, Any
import logging
import time
import re
import pytz

from django.utils import timezone
from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import ScrapingSource, StockData, ScrapingLog


logger = logging.getLogger(__name__)


class StooqCSVScraper:
    """
    CSV-based scraper for stooq.pl using their CSV export endpoint
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.base_url = "https://stooq.pl/q/l/"
        self.session = requests.Session()
        
        # Set up headers to look like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def scrape_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Scrape current stock data for a given symbol from stooq.pl CSV endpoint
        
        CSV Format: Symbol,Data,Czas,Otwarcie,Najwyzszy,Najnizszy,Zamkniecie,Wolumen
        Example: PKN,2025-07-21,17:04:53,87.42,88.26,86.36,86.91,1634376
        """
        # Build CSV export URL: s=symbol, f=fields, h=header, e=csv
        params = {
            's': symbol.lower(),
            'f': 'sd2t2ohlcv',  # Symbol, Date, Time, Open, High, Low, Close, Volume
            'h': '',  # Include header
            'e': 'csv'  # CSV format
        }

        try:
            logger.info(f"Scraping stock data for {symbol} from stooq.pl CSV endpoint")
            logger.debug(f"Request URL: {self.base_url} with params: {params}")
            
            # Create a fresh session for each request to avoid session-based blocking
            fresh_session = requests.Session()
            fresh_session.headers.update(self.session.headers)
            
            response = fresh_session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            logger.debug(f"Response status: {response.status_code}, length: {len(response.text)}")
            
            # Check for rate limit response
            if "Przekroczony dzienny limit" in response.text:
                logger.warning(f"Stooq API rate limit exceeded for {symbol}")
                return None
            
            # Parse CSV data
            csv_data = response.text.strip()
            logger.debug(f"Raw CSV response for {symbol}: '{csv_data}'")
            if not csv_data:
                logger.error(f"Empty response for {symbol}")
                return None
            
            # Parse CSV
            csv_reader = csv.DictReader(StringIO(csv_data))
            rows = list(csv_reader)
            logger.debug(f"Parsed {len(rows)} CSV rows for {symbol}")
            
            if not rows:
                logger.error(f"No data rows found for {symbol}")
                logger.debug(f"Raw CSV response for {symbol}: {csv_data[:200]}...")
                return None
            
            # Get the first (and should be only) data row
            row = rows[0]
            
            # Extract and convert data
            data = self._parse_csv_row(row, symbol.upper())
            data['symbol'] = symbol.upper()
            data['scraped_at'] = timezone.now()
            data['source_url'] = response.url
            
            logger.info(f"Successfully scraped data for {symbol}: {data.get('close_price')}")
            return data
            
        except requests.RequestException as e:
            logger.error(f"HTTP error while scraping {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while scraping {symbol}: {e}")
            return None

    def _parse_csv_row(self, row: Dict[str, str], symbol: str) -> Dict[str, Any]:
        """Parse CSV row into structured data."""
        data = {}
        
        try:
            # Parse prices
            if 'Otwarcie' in row and row['Otwarcie']:
                data['open_price'] = self._parse_decimal(row['Otwarcie'])
            
            if 'Najwyzszy' in row and row['Najwyzszy']:
                data['high_price'] = self._parse_decimal(row['Najwyzszy'])
            
            if 'Najnizszy' in row and row['Najnizszy']:
                data['low_price'] = self._parse_decimal(row['Najnizszy'])
            
            if 'Zamkniecie' in row and row['Zamkniecie']:
                data['close_price'] = self._parse_decimal(row['Zamkniecie'])
            
            # Parse volume
            if 'Wolumen' in row and row['Wolumen']:
                volume_str = row['Wolumen'].strip()
                if volume_str and volume_str != '0':
                    try:
                        data['volume'] = int(volume_str)
                    except ValueError as e:
                        logger.warning(f"Could not parse volume '{volume_str}': {e}")
            
            # Parse date and time
            if 'Data' in row and 'Czas' in row:
                date_str = row['Data'].strip()
                time_str = row['Czas'].strip()
                
                if date_str and time_str:
                    data['data_timestamp'] = self._parse_datetime(date_str, time_str)
                else:
                    data['data_timestamp'] = timezone.now()
            else:
                data['data_timestamp'] = timezone.now()
            
            # Calculate price change if we have both prices
            if data.get('close_price') is not None and data.get('open_price') is not None:
                try:
                    # Use Decimal arithmetic to avoid floating point precision issues
                    close_price = data['close_price']
                    open_price = data['open_price']
                    
                    # Ensure we have valid Decimal values (type checking)
                    if isinstance(close_price, Decimal) and isinstance(open_price, Decimal):
                        # Calculate price change using Decimal arithmetic
                        price_change = close_price - open_price
                        data['price_change'] = price_change
                        
                        if open_price != 0:
                            # Calculate percentage change using Decimal arithmetic
                            price_change_percent = (price_change / open_price) * Decimal('100')
                            data['price_change_percent'] = price_change_percent
                        
                except Exception as e:
                    logger.error(f"Error calculating price changes: {e}")
                    data['price_change'] = None
                    data['price_change_percent'] = None
            
            logger.info(f"Parsed CSV data for {symbol}: Open={data.get('open_price')}, "
                       f"High={data.get('high_price')}, Low={data.get('low_price')}, "
                       f"Close={data.get('close_price')}, Volume={data.get('volume')}")
            
        except Exception as e:
            logger.error(f"Error parsing CSV row for {symbol}: {e}")
        
        return data
    
    def _parse_datetime(self, date_str: str, time_str: str) -> Any:
        """Parse date and time strings into timezone-aware datetime.
        
        stooq.pl provides time in Warsaw timezone (Europe/Warsaw).
        We keep it in Warsaw timezone so the stored time matches the actual trading time.
        """
        try:
            # Date format: 2025-07-21, Time format: 17:04:53
            datetime_str = f"{date_str} {time_str}"
            parsed_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            
            # stooq.pl provides time in Warsaw timezone - keep it in Warsaw
            warsaw_tz = pytz.timezone('Europe/Warsaw')
            warsaw_datetime = warsaw_tz.localize(parsed_datetime)
            
            logger.debug(f"Parsed datetime: {datetime_str} (Warsaw) -> {warsaw_datetime} (Warsaw timezone)")
            return warsaw_datetime
            
        except Exception as e:
            logger.warning(f"Could not parse datetime '{date_str} {time_str}': {e}")
            return timezone.now()
    
    def _parse_decimal(self, value: str) -> Optional[Decimal]:
        """Parse decimal value from string."""
        if not value:
            return None
        
        try:
            # Clean the value - remove any non-numeric characters except comma, dot, minus, plus
            cleaned = re.sub(r'[^\d,.-]', '', value.strip())
            
            # Replace comma with dot for decimal separator
            cleaned = cleaned.replace(',', '.')
            
            # Handle sign
            if value.startswith('-') or value.startswith('+'):
                cleaned = value[0] + cleaned
            
            # Validate that we have a valid decimal string
            if not cleaned or cleaned in ['.', '-', '+', '-.', '+.']:
                logger.warning(f"Invalid decimal value after cleaning: '{value}' -> '{cleaned}'")
                return None
            
            return Decimal(cleaned)
            
        except (ValueError, TypeError, Exception) as e:
            logger.warning(f"Could not parse decimal value '{value}': {type(e).__name__}: {e}")
            return None


# Update the StockDataCollector to use the simple scraper
class SimpleStockDataCollector:
    """
    Stock data collector using multiple sources with automatic fallback
    """
    
    def __init__(self):
        # Import here to avoid circular imports
        from apps.scrapers.scraper_manager import scraper_manager
        self.scraper_manager = scraper_manager
        
    def collect_stock_data(self, symbol: str, source_name: str = "auto") -> bool:
        """Collect and store stock data for a single symbol using automatic source selection."""
        try:
            logger.debug(f"Starting collection for {symbol}")
            # Get stock symbol
            try:
                stock = StockSymbol.active.get(symbol=symbol.upper())
                logger.debug(f"Found stock {symbol} in database")
            except StockSymbol.DoesNotExist:
                logger.error(f"Stock symbol {symbol} not found in database")
                return False
            
            # Get current trading session
            trading_session = TradingSession.get_current_session()
            if not trading_session:
                trading_session = TradingSession.create_session_for_date(timezone.now().date())
            
            # Scrape data using automatic source selection
            scraped_data = self.scraper_manager.scrape_stock_data(stock)
            logger.debug(f"Scraped data for {symbol}: {scraped_data is not None}")
            
            if not scraped_data:
                logger.error(f"No scraped data returned for {symbol}")
                # Try to log error to the most likely source that was attempted
                self._log_scraping_error("stooq.pl", f"Failed to scrape data for {symbol}")
                return False
            
            # Determine which source was used
            scraper_used = scraped_data.get('scraper_used', 'unknown')
            source_name_used = self._get_source_name_for_scraper(scraper_used)
            
            # Get or create scraping source
            source, _ = ScrapingSource.objects.get_or_create(
                name=source_name_used,
                defaults={
                    'source_type': scraper_used,
                    'base_url': self._get_base_url_for_scraper(scraper_used),
                    'is_enabled': True
                }
            )
            
            # Prepare JSON data
            raw_data_for_json = scraped_data.copy()
            # Convert special types for JSON serialization
            for key, value in raw_data_for_json.items():
                if isinstance(value, Decimal):
                    raw_data_for_json[key] = str(value)
                elif key == 'data_timestamp' and value:
                    raw_data_for_json[key] = value.isoformat()
                elif key == 'scraped_at' and value:
                    raw_data_for_json[key] = value.isoformat()
                elif key == 'trading_date' and value:
                    raw_data_for_json[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                elif key == 'trading_time' and value:
                    raw_data_for_json[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
            
            # Check if we should update existing data or create new record
            # Now we use data_timestamp instead of trading_session for uniqueness
            # This allows multiple records per day but prevents exact duplicate timestamps
            data_timestamp = scraped_data.get('data_timestamp') or timezone.now()
            
            existing_data = StockData.objects.filter(
                stock=stock,
                data_timestamp=data_timestamp,
                source=source
            ).first()
            
            if existing_data:
                # Update existing data with same timestamp
                for field in ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 
                             'turnover', 'price_change', 'price_change_percent']:
                    if scraped_data.get(field) is not None:
                        setattr(existing_data, field, scraped_data.get(field))
                    
                existing_data.raw_data = raw_data_for_json
                existing_data.save()
                stock_data = existing_data
                logger.info(f"Updated existing data for {symbol} at {data_timestamp}")
            else:
                # Create new data record with unique timestamp
                stock_data = StockData.objects.create(
                    stock=stock,
                    trading_session=trading_session,
                    source=source,
                    open_price=scraped_data.get('open_price'),
                    high_price=scraped_data.get('high_price'),
                    low_price=scraped_data.get('low_price'),
                    close_price=scraped_data.get('close_price'),
                    volume=scraped_data.get('volume'),
                    turnover=scraped_data.get('turnover'),
                    price_change=scraped_data.get('price_change'),
                    price_change_percent=scraped_data.get('price_change_percent'),
                    data_timestamp=data_timestamp,
                    raw_data=raw_data_for_json
                )
                logger.info(f"Created new data record for {symbol} at {data_timestamp}")
            
            self._log_scraping_event(
                source, 
                'INFO', 
                f"Successfully collected data for {symbol}: {stock_data.close_price} at {data_timestamp}"
            )
            
            logger.debug(f"Successfully collected and saved data for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error collecting stock data for {symbol}: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                source = ScrapingSource.objects.filter(name=source_name).first()
                if source:
                    self._log_scraping_event(source, 'ERROR', f"Exception collecting {symbol}: {str(e)}")
            except Exception as log_error:
                logger.error(f"Failed to log scraping event: {log_error}")
            return False
    
    def collect_all_monitored_stocks(self) -> Dict[str, bool]:
        """Collect stock data for all monitored stocks."""
        results = {}
        monitored_stocks = StockSymbol.active.filter(is_monitored=True)
        
        logger.info(f"Starting data collection for {monitored_stocks.count()} monitored stocks")
        
        for i, stock in enumerate(monitored_stocks):
            symbol = stock.symbol
            logger.info(f"Collecting data for {symbol} ({i+1}/{monitored_stocks.count()})")
            
            # Try to collect data with retries
            success = False
            for attempt in range(3):  # 3 attempts
                try:
                    success = self.collect_stock_data(symbol)
                    if success:
                        break
                    else:
                        logger.warning(f"Attempt {attempt + 1} failed for {symbol}")
                        if attempt < 2:  # Don't sleep after last attempt
                            time.sleep(2)  # Wait 2 seconds before retry
                except Exception as e:
                    logger.error(f"Exception on attempt {attempt + 1} for {symbol}: {e}")
                    if attempt < 2:
                        time.sleep(2)
            
            results[symbol] = success
            
            # Add delay between stocks to avoid rate limiting
            # Longer delay if we're failing (might be rate limited)
            if not success:
                logger.warning(f"All attempts failed for {symbol}, sleeping longer...")
                time.sleep(5)  # 5 seconds after failed stock
            else:
                time.sleep(3)  # 3 seconds between successful requests (was 1)
        
        successful = sum(1 for result in results.values() if result)
        total = len(results)
        logger.info(f"Data collection completed: {successful}/{total} successful")
        
        return results
    
    def _get_source_name_for_scraper(self, scraper_name: str) -> str:
        """Get the source name to use in database for a given scraper."""
        mapping = {
            'stooq': 'stooq.pl',
            'bankier': 'bankier.pl',
            'unknown': 'auto-selected'
        }
        return mapping.get(scraper_name, scraper_name)
    
    def _get_base_url_for_scraper(self, scraper_name: str) -> str:
        """Get the base URL for a given scraper."""
        mapping = {
            'stooq': 'https://stooq.pl',
            'bankier': 'https://www.bankier.pl',
        }
        return mapping.get(scraper_name, 'https://unknown.com')
    
    def _log_scraping_error(self, source_name: str, message: str) -> None:
        """Log scraping error when source is not yet created."""
        try:
            source = ScrapingSource.objects.filter(name=source_name).first()
            if source:
                self._log_scraping_event(source, 'ERROR', message)
            else:
                logger.warning(f"Could not log error to non-existent source {source_name}: {message}")
        except Exception as e:
            logger.error(f"Failed to log scraping error: {e}")
    
    def _log_scraping_event(self, source: ScrapingSource, level: str, message: str) -> None:
        """Log scraping event to database."""
        try:
            ScrapingLog.objects.create(
                source=source,
                level=level,
                message=message
            )
        except Exception as e:
            logger.error(f"Failed to log scraping event: {e}")


# Main exports for easy importing
__all__ = [
    'StooqCSVScraper',
    'SimpleStockDataCollector',
]
