"""
Bankier.pl scraper for stock price data.
Provides backup data source when stooq.pl API is rate limited.

This module provides:
- BankierScraper: HTML scraper with JavaScript support for current stock prices from bankier.pl
- Automatic fallback when stooq.pl rate limit is exceeded
"""

import requests
import re
import time
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional, Any
import logging
from bs4 import BeautifulSoup

from django.utils import timezone
from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import ScrapingSource, StockData, ScrapingLog

# Selenium imports for JavaScript rendering
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    pass


logger = logging.getLogger(__name__)


class BankierScraper:
    """
    HTML scraper for bankier.pl stock data as backup for stooq.pl
    Uses Selenium for JavaScript-rendered content
    """
    
    def __init__(self, timeout: int = 30, use_selenium: bool = True):
        self.timeout = timeout
        self.base_url = "https://www.bankier.pl/inwestowanie/profile/quote.html"
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        
        # Set up requests session as fallback
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.bankier.pl/',
        })
        
        if not self.use_selenium:
            logger.warning("Selenium not available, falling back to requests (may not work for JS-rendered content)")
    
    def _get_chrome_driver(self):
        """Get configured Chrome WebDriver instance."""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium not available")
            
        from selenium.webdriver.chrome.options import Options
        from selenium import webdriver
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Disable images and CSS to speed up loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values": {
                "notifications": 2
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        return webdriver.Chrome(options=chrome_options)
    
    def scrape_stock_data(self, symbol: str, bankier_symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Scrape current stock data for a given symbol from bankier.pl
        
        Args:
            symbol: Original stock symbol (e.g., "11B")
            bankier_symbol: Symbol used on bankier.pl (e.g., "11BIT")
        
        Returns:
            Dictionary with stock data or None if failed
        """
        # Use bankier_symbol if provided, otherwise use original symbol
        search_symbol = bankier_symbol if bankier_symbol else symbol
        
        logger.info(f"Scraping stock data for {symbol} (bankier: {search_symbol}) from bankier.pl")
        
        # Try Selenium first, then fallback to requests
        if self.use_selenium:
            try:
                return self._scrape_with_selenium(symbol, search_symbol)
            except Exception as e:
                logger.warning(f"Selenium scraping failed for {symbol}: {e}, falling back to requests")
                
        return self._scrape_with_requests(symbol, search_symbol)
    
    def _scrape_with_selenium(self, symbol: str, search_symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape using Selenium for JavaScript-rendered content."""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium not available")
            
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        
        driver = None
        try:
            driver = self._get_chrome_driver()
            
            url = f"{self.base_url}?symbol={search_symbol}"
            logger.debug(f"Loading URL with Selenium: {url}")
            
            # Add delay to be respectful
            time.sleep(1)
            
            driver.get(url)
            
            # Wait for the price element to load
            try:
                # Wait up to 10 seconds for price element
                wait = WebDriverWait(driver, 10)
                price_element = wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "profilLast"))
                )
                logger.debug("Price element found")
            except TimeoutException:
                logger.warning("Price element not found within timeout")
                return None
            
            # Get page source after JS loading
            html_content = driver.page_source
            
            # Parse the data
            data = self._parse_html_page(html_content, symbol, search_symbol)
            
            if data:
                data['symbol'] = symbol.upper()
                data['scraped_at'] = timezone.now()
                data['source_url'] = url
                data['source'] = 'bankier.pl'
                
                logger.info(f"Successfully scraped data for {symbol} from bankier.pl: {data.get('close_price')}")
                return data
            else:
                logger.error(f"Failed to parse data for {symbol} from bankier.pl")
                return None
                
        except Exception as e:
            logger.error(f"Selenium error while scraping {symbol} from bankier.pl: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _scrape_with_requests(self, symbol: str, search_symbol: str) -> Optional[Dict[str, Any]]:
        """Scrape using requests (fallback method)."""
        params = {
            'symbol': search_symbol
        }

        try:
            logger.debug(f"Request URL: {self.base_url} with params: {params}")
            
            # Add delay to be respectful to bankier.pl
            time.sleep(1)
            
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            
            # Check for 404 (invalid symbol)
            if response.status_code == 404:
                logger.warning(f"Symbol {search_symbol} not found on bankier.pl (404)")
                return None
            
            response.raise_for_status()
            
            logger.debug(f"Response status: {response.status_code}, length: {len(response.text)}")
            
            # Parse HTML data
            data = self._parse_html_page(response.text, symbol, search_symbol)
            
            if data:
                data['symbol'] = symbol.upper()
                data['scraped_at'] = timezone.now()
                data['source_url'] = response.url
                data['source'] = 'bankier.pl'
                
                logger.info(f"Successfully scraped data for {symbol} from bankier.pl: {data.get('close_price')}")
                return data
            else:
                logger.error(f"Failed to parse data for {symbol} from bankier.pl")
                return None
            
        except requests.RequestException as e:
            logger.error(f"HTTP error while scraping {symbol} from bankier.pl: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while scraping {symbol} from bankier.pl: {e}")
            return None

    def _parse_html_page(self, html_content: str, symbol: str, bankier_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Parse HTML page to extract stock data
        
        Expected format:
        - Current price: "187,6000 zł -0,21% -0,4000 zł"
        - Volume info in statistics tables
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            data = {}
            
            # Extract current price from the main price display
            # Look for pattern like "187,6000 zł -0,21% -0,4000 zł"
            price_pattern = r'(\d+,\d+)\s*zł\s*[-+]?[\d,]+%\s*([-+]\d+,\d+)\s*zł'
            price_match = re.search(price_pattern, html_content)
            
            if price_match:
                # Convert Polish decimal format (comma) to Decimal
                price_str = price_match.group(1).replace(',', '.')
                change_str = price_match.group(2).replace(',', '.')
                
                current_price = self._parse_decimal(price_str)
                price_change = self._parse_decimal(change_str)
                
                if current_price:
                    data['close_price'] = current_price
                    logger.debug(f"Extracted price for {symbol}: {current_price}")
                
                if price_change:
                    data['price_change'] = price_change
                    
                    # Calculate percentage change if we have both values
                    if current_price and current_price != 0:
                        # Calculate the previous price: current - change = previous
                        previous_price = current_price - price_change
                        if previous_price != 0:
                            percentage = (price_change / previous_price) * Decimal('100')
                            data['price_change_percent'] = percentage
            
            # Alternative: try to extract just the price without change info
            if 'close_price' not in data:
                simple_price_pattern = r'(\d+,\d+)\s*zł'
                simple_price_match = re.search(simple_price_pattern, html_content)
                
                if simple_price_match:
                    price_str = simple_price_match.group(1).replace(',', '.')
                    current_price = self._parse_decimal(price_str)
                    if current_price:
                        data['close_price'] = current_price
                        logger.debug(f"Extracted simple price for {symbol}: {current_price}")
            
            # Extract volume from statistics table
            # Look for "Wolumen obrotu:" followed by numbers with spaces
            volume_pattern = r'Wolumen obrotu.*?(\d+(?:\s+\d+)*)\s+szt'
            volume_match = re.search(volume_pattern, html_content, re.DOTALL | re.IGNORECASE)
            
            if volume_match:
                # Remove spaces from volume number
                volume_str = volume_match.group(1).replace(' ', '')
                try:
                    data['volume'] = int(volume_str)
                    logger.debug(f"Extracted volume for {symbol}: {data['volume']}")
                except ValueError as e:
                    logger.warning(f"Could not parse volume '{volume_str}': {e}")
            
            # Extract market cap (kapitalizacja) for additional info
            cap_pattern = r'Kapitalizacja.*?(\d+(?:\s+\d+)*(?:,\d+)?)\s+zł'
            cap_match = re.search(cap_pattern, html_content, re.DOTALL | re.IGNORECASE)
            
            if cap_match:
                cap_str = cap_match.group(1).replace(' ', '').replace(',', '.')
                try:
                    # Store as additional info (not required for trading)
                    data['market_cap'] = float(cap_str)
                    logger.debug(f"Extracted market cap for {symbol}: {data['market_cap']}")
                except ValueError:
                    pass
            
            # Set timestamp to current time (bankier.pl shows current data)
            data['data_timestamp'] = timezone.now()
            
            # If we have a close price, we consider the scraping successful
            if 'close_price' in data:
                logger.info(f"Successfully parsed bankier.pl data for {symbol}: "
                           f"Close={data.get('close_price')}, "
                           f"Change={data.get('price_change')}, "
                           f"Volume={data.get('volume')}")
                return data
            else:
                logger.warning(f"Could not find price data for {symbol} on bankier.pl")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing bankier.pl HTML for {symbol}: {e}")
            return None

    def _parse_decimal(self, value: str) -> Optional[Decimal]:
        """Parse string to Decimal, handling various formats."""
        if not value or not isinstance(value, str):
            return None
        
        try:
            # Clean the string: remove spaces and handle Polish decimal format
            cleaned = value.strip().replace(' ', '').replace(',', '.')
            
            # Remove any non-numeric characters except dots and minus signs
            cleaned = re.sub(r'[^\d.-]', '', cleaned)
            
            if cleaned:
                return Decimal(cleaned)
        except Exception as e:
            logger.warning(f"Could not parse decimal '{value}': {e}")
        
        return None

    def is_available(self) -> bool:
        """
        Check if bankier.pl is available by making a test request
        
        Returns:
            True if bankier.pl responds successfully
        """
        try:
            test_url = "https://www.bankier.pl/"
            response = self.session.get(test_url, timeout=10)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.warning(f"Bankier.pl availability check failed: {e}")
            return False

    def get_priority(self) -> int:
        """
        Return priority for this scraper (higher = more preferred)
        Bankier is backup so lower priority than stooq
        
        Returns:
            Priority number (1 = backup, 10 = primary)
        """
        return 1  # Backup scraper
