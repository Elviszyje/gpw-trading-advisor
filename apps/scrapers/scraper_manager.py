"""
Scraper Manager for coordinating multiple stock data sources.
Provides automatic fallback when primary sources are rate limited or unavailable.

This module provides:
- ScraperManager: Orchestrates multiple scrapers with priority-based selection
- Automatic fallback handling when scrapers fail or are rate limited
- Source preference management and status tracking
"""

import logging
from typing import Dict, List, Optional, Any, Type
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache

from apps.core.models import StockSymbol
from apps.scrapers.models import ScrapingSource, StockData
from apps.scrapers.scraping import StooqCSVScraper
from apps.scrapers.bankier_scraper import BankierScraper


logger = logging.getLogger(__name__)


class ScraperManager:
    """
    Manages multiple stock data scrapers with automatic fallback logic.
    """
    
    def __init__(self):
        self.scrapers = {
            'stooq': StooqCSVScraper(),
            'bankier': BankierScraper(),
        }
        
        # Priority order: higher = more preferred
        # stooq is preferred (CSV API, more reliable data)
        # bankier is fallback (HTML scraping)
        self.scraper_priorities = {
            'stooq': 10,     # Primary - CSV API with historical data
            'bankier': 1,    # Backup - HTML scraping, current data only
        }
        
        # Rate limit tracking
        self.rate_limit_cache_key = "scraper_rate_limits"
        self.rate_limit_duration = timedelta(hours=1)  # How long to remember rate limits

    def scrape_stock_data(self, stock_symbol: StockSymbol, force_source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Scrape stock data with automatic fallback between sources.
        
        Args:
            stock_symbol: StockSymbol instance to scrape
            force_source: Force use of specific scraper ('stooq' or 'bankier')
            
        Returns:
            Dictionary with scraped data or None if all sources fail
        """
        symbol = stock_symbol.symbol
        
        if force_source:
            if force_source not in self.scrapers:
                logger.error(f"Unknown forced source '{force_source}' for {symbol}")
                return None
            
            return self._try_scraper(force_source, stock_symbol)
        
        # Get available scrapers sorted by priority (highest first)
        available_scrapers = self._get_available_scrapers()
        
        logger.info(f"Scraping {symbol} with {len(available_scrapers)} available sources: {list(available_scrapers.keys())}")
        
        for scraper_name in available_scrapers:
            result = self._try_scraper(scraper_name, stock_symbol)
            
            if result:
                logger.info(f"Successfully scraped {symbol} using {scraper_name}")
                return result
            
            # If we get rate limited, mark this scraper as temporarily unavailable
            if self._is_rate_limited_error(scraper_name):
                self._mark_rate_limited(scraper_name)
                logger.warning(f"Scraper {scraper_name} hit rate limit, marking as unavailable")
        
        logger.error(f"All scrapers failed for symbol {symbol}")
        return None

    def _try_scraper(self, scraper_name: str, stock_symbol: StockSymbol) -> Optional[Dict[str, Any]]:
        """
        Attempt to scrape data using specific scraper.
        
        Args:
            scraper_name: Name of the scraper to use
            stock_symbol: StockSymbol instance to scrape
            
        Returns:
            Scraped data or None if failed
        """
        if scraper_name not in self.scrapers:
            logger.error(f"Unknown scraper: {scraper_name}")
            return None
        
        scraper = self.scrapers[scraper_name]
        symbol = stock_symbol.symbol
        
        try:
            logger.debug(f"Trying scraper {scraper_name} for {symbol}")
            
            if scraper_name == 'stooq':
                # Use stooq CSV scraper
                result = scraper.scrape_stock_data(symbol)
            elif scraper_name == 'bankier':
                # Use bankier HTML scraper with symbol mapping
                bankier_symbol = stock_symbol.bankier_symbol or symbol
                result = scraper.scrape_stock_data(symbol, bankier_symbol)
            else:
                logger.error(f"No handler for scraper type: {scraper_name}")
                return None
            
            if result:
                # Add source information to result
                result['scraper_used'] = scraper_name
                logger.debug(f"Scraper {scraper_name} returned data for {symbol}")
                return result
            else:
                logger.debug(f"Scraper {scraper_name} returned no data for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error using scraper {scraper_name} for {symbol}: {e}")
            return None

    def _get_available_scrapers(self) -> Dict[str, int]:
        """
        Get scrapers that are currently available (not rate limited).
        
        Returns:
            Dict mapping scraper names to priorities, sorted by priority (desc)
        """
        rate_limited = self._get_rate_limited_scrapers()
        
        available = {}
        for name, priority in self.scraper_priorities.items():
            if name not in rate_limited:
                # Check if scraper is actually available
                try:
                    scraper = self.scrapers[name]
                    if hasattr(scraper, 'is_available') and not scraper.is_available():
                        logger.debug(f"Scraper {name} reports unavailable")
                        continue
                    
                    available[name] = priority
                except Exception as e:
                    logger.warning(f"Error checking availability for scraper {name}: {e}")
        
        # Sort by priority (highest first)
        return dict(sorted(available.items(), key=lambda x: x[1], reverse=True))

    def _get_rate_limited_scrapers(self) -> List[str]:
        """
        Get list of scrapers that are currently rate limited.
        
        Returns:
            List of scraper names that are rate limited
        """
        rate_limits = cache.get(self.rate_limit_cache_key, {})
        current_time = timezone.now()
        
        # Filter out expired rate limits
        active_limits = []
        updated_limits = {}
        
        for scraper_name, limit_time in rate_limits.items():
            if isinstance(limit_time, str):
                # Convert string timestamp back to datetime
                try:
                    limit_time = datetime.fromisoformat(limit_time.replace('Z', '+00:00'))
                except:
                    continue
            
            if current_time - limit_time < self.rate_limit_duration:
                active_limits.append(scraper_name)
                updated_limits[scraper_name] = limit_time.isoformat()
        
        # Update cache with cleaned data
        if updated_limits != rate_limits:
            cache.set(self.rate_limit_cache_key, updated_limits, timeout=3600)
        
        return active_limits

    def _mark_rate_limited(self, scraper_name: str) -> None:
        """
        Mark a scraper as rate limited.
        
        Args:
            scraper_name: Name of the scraper to mark
        """
        rate_limits = cache.get(self.rate_limit_cache_key, {})
        rate_limits[scraper_name] = timezone.now().isoformat()
        cache.set(self.rate_limit_cache_key, rate_limits, timeout=3600)
        
        logger.warning(f"Marked scraper {scraper_name} as rate limited until {timezone.now() + self.rate_limit_duration}")

    def _is_rate_limited_error(self, scraper_name: str) -> bool:
        """
        Check if the last error from a scraper indicates rate limiting.
        
        Args:
            scraper_name: Name of the scraper to check
            
        Returns:
            True if the scraper appears to be rate limited
        """
        # For stooq, we could check for specific HTTP status codes or error messages
        # For now, we'll use a simple heuristic based on the scraper type
        
        if scraper_name == 'stooq':
            # stooq has 200 requests/day limit
            # We could track request count or look for 429 errors
            # For now, assume any failure might be rate limiting during heavy usage
            return True
        elif scraper_name == 'bankier':
            # bankier doesn't have explicit rate limits but we should be respectful
            # Only mark as rate limited if we get specific HTTP errors
            return False
        
        return False

    def get_scraper_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all scrapers.
        
        Returns:
            Dict with scraper names as keys and status info as values
        """
        status = {}
        rate_limited = self._get_rate_limited_scrapers()
        
        for name, priority in self.scraper_priorities.items():
            scraper = self.scrapers[name]
            
            scraper_status = {
                'priority': priority,
                'is_rate_limited': name in rate_limited,
                'is_available': True,
                'last_check': None,
            }
            
            # Check availability if scraper supports it
            try:
                if hasattr(scraper, 'is_available'):
                    scraper_status['is_available'] = scraper.is_available()
                    scraper_status['last_check'] = timezone.now().isoformat()
            except Exception as e:
                scraper_status['is_available'] = False
                scraper_status['error'] = str(e)
            
            status[name] = scraper_status
        
        return status

    def reset_rate_limits(self) -> None:
        """
        Clear all rate limit restrictions.
        Useful for testing or manual reset.
        """
        cache.delete(self.rate_limit_cache_key)
        logger.info("Cleared all scraper rate limit restrictions")

    def force_rate_limit(self, scraper_name: str) -> None:
        """
        Force a scraper to be marked as rate limited.
        Useful for testing fallback behavior.
        
        Args:
            scraper_name: Name of scraper to rate limit
        """
        if scraper_name in self.scrapers:
            self._mark_rate_limited(scraper_name)
            logger.info(f"Forced rate limit on scraper {scraper_name}")
        else:
            logger.error(f"Cannot rate limit unknown scraper: {scraper_name}")


# Global instance for easy access
scraper_manager = ScraperManager()
