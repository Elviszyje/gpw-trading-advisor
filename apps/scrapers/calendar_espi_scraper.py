"""
Company calendar and ESPI communications scraper.
Handles corporate events, earnings calendars, and ESPI reports.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import logging
import time
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Data structure for calendar events."""
    stock_symbol: str
    event_type: str
    title: str
    description: str
    event_date: datetime
    impact_level: str
    source_url: str
    financial_details: Dict[str, Any]


@dataclass
class ESPIReport:
    """Data structure for ESPI reports."""
    stock_symbol: str
    report_type: str
    report_number: str
    title: str
    content: str
    publication_date: datetime
    espi_url: str
    importance_level: str


class CompanyCalendarScraper:
    """
    Scraper for company calendar events and corporate actions.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GPW Trading Advisor Calendar Scraper 1.0'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_delay = 2.0
        
        # Source configurations for calendar data
        self.calendar_sources = {
            'stooq_calendar': {
                'base_url': 'https://stooq.pl',
                'calendar_url': 'https://stooq.pl/q/n/?s={symbol}&c=0',
                'events_selector': '.tab div',
                'date_format': '%Y-%m-%d',
            },
            'gpw_calendar': {
                'base_url': 'https://www.gpw.pl',
                'calendar_url': 'https://www.gpw.pl/calendar',
                'events_selector': '.calendar-event',
            }
        }
    
    def _rate_limit(self) -> None:
        """Implement rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_delay:
            sleep_time = self.min_delay - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """Make HTTP request with rate limiting."""
        try:
            self._rate_limit()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.debug(f"Successfully fetched calendar: {url}")
            return soup
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch calendar {url}: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None
        
        patterns = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d.%m.%Y %H:%M',
            '%d.%m.%Y',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
        ]
        
        for pattern in patterns:
            try:
                return datetime.strptime(date_str.strip(), pattern)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _determine_impact_level(self, event_type: str, title: str) -> str:
        """Determine impact level based on event type and content."""
        title_lower = title.lower()
        
        # Critical impact events
        if event_type in ['earnings', 'merger', 'ipo', 'delisting']:
            return 'critical'
        
        # High impact events
        if event_type in ['dividend', 'agm', 'split']:
            return 'high'
        
        # Check title for impact indicators
        high_impact_keywords = ['przejęcie', 'fuzja', 'dywidenda', 'emisja', 'wykup']
        if any(keyword in title_lower for keyword in high_impact_keywords):
            return 'high'
        
        medium_impact_keywords = ['raport', 'wyniki', 'sprawozdanie']
        if any(keyword in title_lower for keyword in medium_impact_keywords):
            return 'medium'
        
        return 'medium'  # Default
    
    def _classify_event_type(self, title: str, description: str) -> str:
        """Classify event type based on title and description."""
        text = f"{title} {description}".lower()
        
        if any(word in text for word in ['wyniki', 'raport', 'sprawozdanie']):
            return 'earnings'
        elif any(word in text for word in ['dywidenda', 'dividend']):
            return 'dividend'
        elif any(word in text for word in ['walne zgromadzenie', 'agm']):
            return 'agm'
        elif any(word in text for word in ['konferencja', 'conference']):
            return 'conference'
        elif any(word in text for word in ['split', 'podział']):
            return 'split'
        elif any(word in text for word in ['przejęcie', 'merger', 'fuzja']):
            return 'merger'
        elif any(word in text for word in ['ipo', 'debiut']):
            return 'ipo'
        else:
            return 'other'
    
    def scrape_company_calendar(self, stock_symbol: str, days_ahead: int = 30) -> List[CalendarEvent]:
        """Scrape calendar events for a specific company."""
        events = []
        
        # Try to scrape from stooq calendar
        stooq_events = self._scrape_stooq_calendar(stock_symbol, days_ahead)
        events.extend(stooq_events)
        
        return events
    
    def _scrape_stooq_calendar(self, stock_symbol: str, days_ahead: int) -> List[CalendarEvent]:
        """Scrape calendar events from stooq.pl."""
        events = []
        config = self.calendar_sources['stooq_calendar']
        
        # Construct URL for specific stock
        url = config['calendar_url'].format(symbol=stock_symbol.lower())
        soup = self._make_request(url)
        
        if not soup:
            return events
        
        try:
            # Look for calendar events (this would need to be adapted based on actual stooq structure)
            event_elements = soup.select('.news-item, .event-item, tr')
            
            for element in event_elements:
                try:
                    # Extract event information (simplified example)
                    title_elem = element.select_one('a, .title, td')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    
                    # Try to extract date
                    date_text = ""
                    date_elem = element.select_one('.date, time, td:first-child')
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                    
                    event_date = self._parse_date(date_text)
                    if not event_date:
                        # If no date found, skip
                        continue
                    
                    # Only include future events within the specified range
                    if event_date < datetime.now():
                        continue
                    
                    if event_date > datetime.now() + timedelta(days=days_ahead):
                        continue
                    
                    # Extract description
                    desc_elem = element.select_one('.description, .summary')
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # Classify event
                    event_type = self._classify_event_type(title, description)
                    impact_level = self._determine_impact_level(event_type, title)
                    
                    # Extract source URL
                    link_elem = element.select_one('a')
                    href = link_elem.get('href') if link_elem else None
                    source_url = urljoin(config['base_url'], str(href)) if href else url
                    
                    event = CalendarEvent(
                        stock_symbol=stock_symbol,
                        event_type=event_type,
                        title=title,
                        description=description,
                        event_date=event_date,
                        impact_level=impact_level,
                        source_url=source_url,
                        financial_details={}
                    )
                    
                    events.append(event)
                    logger.info(f"Found calendar event: {title} for {stock_symbol}")
                    
                except Exception as e:
                    logger.warning(f"Error parsing calendar event: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error scraping stooq calendar for {stock_symbol}: {e}")
        
        return events


class ESPIScraper:
    """
    Scraper for ESPI/EBI reports from Polish stock exchange.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GPW Trading Advisor ESPI Scraper 1.0'
        })
        
        # ESPI sources
        self.espi_sources = {
            'gpw_espi': {
                'base_url': 'https://www.gpw.pl',
                'espi_search': 'https://www.gpw.pl/espi-search?phrase={symbol}',
                'report_selector': '.espi-report',
            },
            'infostrefa_espi': {
                'base_url': 'https://infostrefa.com',
                'espi_feed': 'https://infostrefa.com/espi/rss',
                'symbol_filter': '{symbol}',
            }
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_delay = 3.0  # Longer delay for ESPI to be respectful
    
    def _rate_limit(self) -> None:
        """Implement rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_delay:
            sleep_time = self.min_delay - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """Make HTTP request with rate limiting."""
        try:
            self._rate_limit()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.debug(f"Successfully fetched ESPI: {url}")
            return soup
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch ESPI {url}: {e}")
            return None
    
    def _determine_importance(self, title: str, content: str) -> str:
        """Determine importance level of ESPI report."""
        text = f"{title} {content}".lower()
        
        # Critical importance indicators
        critical_keywords = [
            'przejęcie', 'fuzja', 'emisja akcji', 'wykup', 'upadłość',
            'zawieszenie', 'delisting', 'znacząca umowa'
        ]
        if any(keyword in text for keyword in critical_keywords):
            return 'critical'
        
        # High importance indicators
        high_keywords = [
            'wyniki finansowe', 'dywidenda', 'raport kwartalny',
            'sprawozdanie roczne', 'prognoza', 'rekomendacja'
        ]
        if any(keyword in text for keyword in high_keywords):
            return 'high'
        
        # Medium importance (default for most reports)
        return 'medium'
    
    def _classify_report_type(self, title: str, report_number: str) -> str:
        """Classify ESPI report type."""
        title_lower = title.lower()
        
        if 'rb' in report_number.lower() or 'kwartalny' in title_lower:
            return 'rb'
        elif 'rs' in report_number.lower() or 'roczny' in title_lower:
            return 'rs'
        elif 'ebi' in report_number.lower():
            return 'ebi'
        else:
            return 'espi'
    
    def scrape_recent_espi_reports(self, stock_symbol: str, days_back: int = 7) -> List[ESPIReport]:
        """Scrape recent ESPI reports for a specific company."""
        reports = []
        
        # This is a simplified implementation
        # In reality, you would need to adapt to the actual ESPI system structure
        try:
            # Mock implementation - in real scenario you'd connect to actual ESPI feeds
            logger.info(f"Scraping ESPI reports for {stock_symbol} (last {days_back} days)")
            
            # Example of how you might structure this:
            # 1. Connect to GPW ESPI RSS feed
            # 2. Filter by stock symbol
            # 3. Parse report content
            # 4. Extract key information
            
            # For demonstration, create a mock report
            mock_report = ESPIReport(
                stock_symbol=stock_symbol,
                report_type='espi',
                report_number='1/2025',
                title=f'Raport bieżący spółki {stock_symbol}',
                content='Treść raportu ESPI...',
                publication_date=datetime.now(),
                espi_url=f'https://www.gpw.pl/espi/{stock_symbol}',
                importance_level='medium'
            )
            
            reports.append(mock_report)
            
        except Exception as e:
            logger.error(f"Error scraping ESPI for {stock_symbol}: {e}")
        
        return reports


class CalendarDatabase:
    """Database operations for calendar events."""
    
    @staticmethod
    def save_events(events: List[CalendarEvent]) -> int:
        """Save calendar events to database."""
        from apps.scrapers.models import CompanyCalendarEvent
        from apps.core.models import StockSymbol
        
        saved_count = 0
        
        for event in events:
            try:
                stock = StockSymbol.objects.get(symbol=event.stock_symbol)
                
                # Check if event already exists
                existing = CompanyCalendarEvent.objects.filter(
                    stock_symbol=stock,
                    title=event.title,
                    event_date=event.event_date
                ).first()
                
                if not existing:
                    calendar_event = CompanyCalendarEvent(
                        stock_symbol=stock,
                        event_type=event.event_type,
                        title=event.title,
                        description=event.description,
                        event_date=event.event_date,
                        impact_level=event.impact_level,
                        source_url=event.source_url,
                        is_confirmed=True
                    )
                    calendar_event.save()
                    saved_count += 1
                    logger.info(f"Saved calendar event: {event.title}")
                
            except StockSymbol.DoesNotExist:
                logger.warning(f"Stock symbol {event.stock_symbol} not found in database")
            except Exception as e:
                logger.error(f"Error saving calendar event: {e}")
        
        return saved_count


class ESPIDatabase:
    """Database operations for ESPI reports."""
    
    @staticmethod
    def save_reports(reports: List[ESPIReport]) -> int:
        """Save ESPI reports to database."""
        from apps.scrapers.models import ESPIReport as ESPIReportModel
        from apps.core.models import StockSymbol
        
        saved_count = 0
        
        for report in reports:
            try:
                stock = StockSymbol.objects.get(symbol=report.stock_symbol)
                
                # Check if report already exists
                existing = ESPIReportModel.objects.filter(
                    stock_symbol=stock,
                    report_number=report.report_number
                ).first()
                
                if not existing:
                    espi_report = ESPIReportModel(
                        stock_symbol=stock,
                        report_type=report.report_type,
                        report_number=report.report_number,
                        title=report.title,
                        content=report.content,
                        publication_date=report.publication_date,
                        espi_url=report.espi_url,
                        importance_level=report.importance_level
                    )
                    espi_report.save()
                    saved_count += 1
                    logger.info(f"Saved ESPI report: {report.title}")
                
            except StockSymbol.DoesNotExist:
                logger.warning(f"Stock symbol {report.stock_symbol} not found in database")
            except Exception as e:
                logger.error(f"Error saving ESPI report: {e}")
        
        return saved_count


# Usage functions
def collect_company_calendar_data(symbol: Optional[str] = None, days_ahead: int = 30):
    """Collect company calendar data for all or specific symbols."""
    scraper = CompanyCalendarScraper()
    
    if symbol:
        symbols = [symbol]
    else:
        from apps.core.models import StockSymbol
        symbols = list(StockSymbol.objects.values_list('symbol', flat=True))
    
    all_events = []
    for stock_symbol in symbols:
        events = scraper.scrape_company_calendar(stock_symbol, days_ahead)
        all_events.extend(events)
    
    if all_events:
        saved_count = CalendarDatabase.save_events(all_events)
        logger.info(f"Collected {len(all_events)} calendar events, saved {saved_count} new ones")
        return saved_count
    else:
        logger.info("No calendar events found")
        return 0


def collect_espi_reports(symbol: Optional[str] = None, days_back: int = 7):
    """Collect ESPI reports for all or specific symbols."""
    scraper = ESPIScraper()
    
    if symbol:
        symbols = [symbol]
    else:
        from apps.core.models import StockSymbol
        symbols = list(StockSymbol.objects.values_list('symbol', flat=True))
    
    all_reports = []
    for stock_symbol in symbols:
        reports = scraper.scrape_recent_espi_reports(stock_symbol, days_back)
        all_reports.extend(reports)
    
    if all_reports:
        saved_count = ESPIDatabase.save_reports(all_reports)
        logger.info(f"Collected {len(all_reports)} ESPI reports, saved {saved_count} new ones")
        return saved_count
    else:
        logger.info("No ESPI reports found")
        return 0
