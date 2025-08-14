"""
Enhanced Bankier Calendar Scraper with Date Range Support and Change Tracking
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
import re
import time
import logging
from urllib.parse import urljoin
from dataclasses import dataclass

from django.utils import timezone
from django.db import transaction
from apps.core.models import StockSymbol
from news.models import CompanyCalendarEvent, EventDateChange, CalendarScrapingJob


logger = logging.getLogger(__name__)


@dataclass
class ScrapedEvent:
    """Data class for scraped calendar events"""
    title: str
    description: str
    event_date: date
    event_type: str
    stock_symbol: Optional[str] = None
    dividend_amount: Optional[float] = None
    dividend_currency: str = 'PLN'
    source_url: str = ''
    market_impact: str = 'unknown'


class EnhancedBankierCalendarScraper:
    """
    Enhanced calendar scraper with date range support and change tracking
    """
    
    BASE_URL = 'https://www.bankier.pl/gielda/kalendarium'
    
    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize scraper with rate limiting
        
        Args:
            rate_limit: Seconds to wait between requests
        """
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Statistics
        self.stats = {
            'events_found': 0,
            'events_created': 0,
            'events_updated': 0,
            'date_changes_detected': 0,
            'errors': [],
        }
    
    def scrape_date_range(
        self, 
        start_date: date, 
        end_date: date,
        job: Optional[CalendarScrapingJob] = None
    ) -> Dict[str, Any]:
        """
        Scrape calendar events for a date range
        
        Args:
            start_date: Start date for scraping
            end_date: End date for scraping
            job: Optional scraping job for progress tracking
            
        Returns:
            Dictionary with scraping results and statistics
        """
        logger.info(f"Starting calendar scrape from {start_date} to {end_date}")
        
        if job:
            job.status = 'running'
            job.started_at = timezone.now()
            job.save()
        
        try:
            # Reset statistics
            self.stats = {
                'events_found': 0,
                'events_created': 0,
                'events_updated': 0,
                'date_changes_detected': 0,
                'errors': [],
            }
            
            # Generate week ranges to scrape
            week_ranges = self._generate_week_ranges(start_date, end_date)
            
            for week_start, week_end in week_ranges:
                try:
                    week_url = f"{self.BASE_URL}/{week_start.strftime('%Y-%m-%d')}"
                    logger.info(f"Scraping week: {week_start} to {week_end} from {week_url}")
                    
                    # Scrape events for this week
                    week_events = self._scrape_week(week_url, week_start, week_end)
                    
                    # Process and save events
                    self._process_events(week_events)
                    
                    # Update job progress if available
                    if job:
                        job.logs += f"Completed week {week_start} - {week_end}: {len(week_events)} events\n"
                        job.save()
                    
                    # Rate limiting
                    time.sleep(self.rate_limit)
                    
                except Exception as e:
                    error_msg = f"Error scraping week {week_start}: {str(e)}"
                    logger.error(error_msg)
                    self.stats['errors'].append(error_msg)
                    
                    if job:
                        job.error_message += f"{error_msg}\n"
                        job.save()
            
            # Final statistics
            result = {
                'success': True,
                'events_found': self.stats['events_found'],
                'events_created': self.stats['events_created'],
                'events_updated': self.stats['events_updated'],
                'date_changes_detected': self.stats['date_changes_detected'],
                'errors': self.stats['errors'],
                'date_range': f"{start_date} to {end_date}",
            }
            
            if job:
                job.status = 'completed'
                job.completed_at = timezone.now()
                job.events_found = self.stats['events_found']
                job.events_created = self.stats['events_created']
                job.events_updated = self.stats['events_updated']
                job.date_changes_detected = self.stats['date_changes_detected']
                if self.stats['errors']:
                    job.error_message = '\n'.join(self.stats['errors'])
                job.save()
            
            logger.info(f"Scraping completed: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Critical error during scraping: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if job:
                job.status = 'failed'
                job.completed_at = timezone.now()
                job.error_message = error_msg
                job.save()
            
            return {
                'success': False,
                'error': error_msg,
                'events_found': self.stats['events_found'],
                'events_created': self.stats['events_created'],
                'events_updated': self.stats['events_updated'],
            }
    
    def _generate_week_ranges(self, start_date: date, end_date: date) -> List[Tuple[date, date]]:
        """Generate list of week ranges to scrape"""
        week_ranges = []
        current_date = start_date
        
        while current_date <= end_date:
            # Find Monday of current week
            week_start = current_date - timedelta(days=current_date.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Adjust to stay within requested range
            week_start = max(week_start, start_date)
            week_end = min(week_end, end_date)
            
            week_ranges.append((week_start, week_end))
            
            # Move to next week
            current_date = week_end + timedelta(days=1)
        
        return week_ranges
    
    def _scrape_week(self, url: str, week_start: date, week_end: date) -> List[ScrapedEvent]:
        """Scrape events for a single week"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = []
            
            # Find all calendar events for the week
            # This uses the same parsing logic as before but for a specific week
            calendar_container = soup.find('div', class_='kalendarium') or soup.find('main')
            
            if not calendar_container:
                logger.warning(f"No calendar container found for {url}")
                return events
            
            # Parse each day in the week
            for single_date in self._daterange(week_start, week_end):
                day_events = self._parse_day_events(calendar_container, single_date, url)
                events.extend(day_events)
            
            self.stats['events_found'] += len(events)
            logger.info(f"Found {len(events)} events for week {week_start} - {week_end}")
            
            return events
            
        except requests.RequestException as e:
            error_msg = f"HTTP error scraping {url}: {str(e)}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
            return []
        except Exception as e:
            error_msg = f"Parsing error for {url}: {str(e)}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
            return []
    
    def _daterange(self, start_date: date, end_date: date):
        """Generate date range day by day"""
        for n in range(int((end_date - start_date).days) + 1):
            yield start_date + timedelta(n)
    
    def _parse_day_events(self, container: BeautifulSoup, target_date: date, source_url: str) -> List[ScrapedEvent]:
        """Parse events for a specific day"""
        events = []
        
        # Look for date headers and events
        date_str = target_date.strftime('%d.%m')  # DD.MM format
        alt_date_str = target_date.strftime('%d %B')  # DD Month format (Polish)
        
        # Find events for this specific date
        # This is a simplified version - you'd adapt based on actual HTML structure
        event_elements = container.find_all('div', class_='event') or container.find_all('tr')
        
        for element in event_elements:
            try:
                event = self._parse_event_element(element, target_date, source_url)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Error parsing event element: {str(e)}")
                continue
        
        return events
    
    def _parse_event_element(self, element: BeautifulSoup, target_date: date, source_url: str) -> Optional[ScrapedEvent]:
        """Parse individual event element - using existing logic"""
        # This would use the same parsing logic from the original scraper
        # Adapted to work with the new structure
        
        text_content = element.get_text(strip=True)
        if not text_content:
            return None
        
        # Extract stock symbol
        stock_symbol = self._extract_stock_symbol(text_content)
        if not stock_symbol:
            return None
        
        # Determine event type and extract details
        event_type = self._classify_event_from_text(text_content)
        title = self._extract_title(text_content)
        description = text_content
        
        # Extract dividend information if applicable
        dividend_amount = None
        if 'dywidend' in text_content.lower():
            dividend_amount = self._extract_dividend_amount(text_content)
        
        # Assess market impact
        market_impact = self._assess_market_impact(event_type, text_content)
        
        return ScrapedEvent(
            title=title,
            description=description,
            event_date=target_date,
            event_type=event_type,
            stock_symbol=stock_symbol,
            dividend_amount=dividend_amount,
            source_url=source_url,
            market_impact=market_impact
        )
    
    def _process_events(self, events: List[ScrapedEvent]):
        """Process and save scraped events to database"""
        for event_data in events:
            try:
                self._save_event(event_data)
            except Exception as e:
                error_msg = f"Error saving event {event_data.title}: {str(e)}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
    
    @transaction.atomic
    def _save_event(self, event_data: ScrapedEvent):
        """Save individual event to database with change tracking"""
        # Get or create stock symbol
        if not event_data.stock_symbol:
            return
        
        stock, created = StockSymbol.objects.get_or_create(
            symbol=event_data.stock_symbol,
            defaults={'company_name': event_data.stock_symbol}
        )
        
        # Check if event already exists
        existing_event = CompanyCalendarEvent.objects.filter(
            stock=stock,
            title=event_data.title,
            event_type=event_data.event_type
        ).first()
        
        if existing_event:
            # Check for date changes
            if existing_event.event_date != event_data.event_date:
                # Date change detected!
                self._track_date_change(existing_event, event_data.event_date)
                existing_event.event_date = event_data.event_date
                existing_event.save()
                self.stats['events_updated'] += 1
                self.stats['date_changes_detected'] += 1
                logger.info(f"Date change detected for {stock.symbol} - {event_data.title}")
            else:
                # Update other fields if needed
                existing_event.description = event_data.description
                existing_event.source_url = event_data.source_url
                existing_event.last_verified = timezone.now()
                existing_event.save()
                self.stats['events_updated'] += 1
        else:
            # Create new event
            CompanyCalendarEvent.objects.create(
                stock=stock,
                title=event_data.title,
                description=event_data.description,
                event_type=event_data.event_type,
                event_date=event_data.event_date,
                original_date=event_data.event_date,
                dividend_amount=event_data.dividend_amount,
                dividend_currency=event_data.dividend_currency,
                source_url=event_data.source_url,
                market_impact=event_data.market_impact,
                is_confirmed=False
            )
            self.stats['events_created'] += 1
            logger.info(f"Created new event: {stock.symbol} - {event_data.title}")
    
    def _track_date_change(self, existing_event: CompanyCalendarEvent, new_date: date):
        """Track date change for sentiment analysis"""
        old_date = existing_event.event_date
        
        # Determine change type
        if new_date > old_date:
            change_type = 'postponed'
            sentiment_impact = 'negative'  # Generally negative
        elif new_date < old_date:
            change_type = 'advanced'
            sentiment_impact = 'neutral'  # Could be positive or neutral
        else:
            change_type = 'confirmed'
            sentiment_impact = 'neutral'
        
        # Create change record
        EventDateChange.objects.create(
            event=existing_event,
            old_date=old_date,
            new_date=new_date,
            change_type=change_type,
            sentiment_impact=sentiment_impact,
            change_reason='Date modification detected during scraping'
        )
    
    # Reuse existing helper methods from original scraper
    def _extract_stock_symbol(self, text: str) -> Optional[str]:
        """Extract stock symbol from text"""
        # Implement existing logic
        pass
    
    def _classify_event_from_text(self, text: str) -> str:
        """Classify event type from text"""
        # Implement existing logic
        pass
    
    def _extract_title(self, text: str) -> str:
        """Extract event title from text"""
        # Implement existing logic
        pass
    
    def _extract_dividend_amount(self, text: str) -> Optional[float]:
        """Extract dividend amount from text"""
        # Implement existing logic
        pass
    
    def _assess_market_impact(self, event_type: str, text: str) -> str:
        """Assess market impact of event"""
        # Implement existing logic
        pass
