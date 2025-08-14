"""
Scraper kalendarza wydarzeń z Bankier.pl
Pobiera prawdziwe dane o wydarzeniach spółek GPW
"""

import requests
from bs4 import BeautifulSoup
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import re
import time
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importy Django będą działać po konfiguracji
# from core.models import StockSymbol
# from news.models import CompanyCalendarEvent

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CalendarEvent:
    """Struktura danych wydarzenia kalendarzowego"""
    date: datetime
    company_symbol: str
    company_name: str
    event_type: str
    event_category: str
    description: str
    impact_level: str
    source_url: str

class BankierCalendarScraper:
    """Scraper kalendarza wydarzeń z Bankier.pl"""
    
    def __init__(self):
        self.base_url = "https://www.bankier.pl/gielda/kalendarium"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Kategorie wydarzeń dostępne na Bankier.pl
        self.event_categories = {
            'dywidendy': 'DIVIDEND',
            'wza': 'SHAREHOLDER_MEETING', 
            'wyniki': 'EARNINGS',
            'rynek-pierwotny': 'IPO',
            'inne': 'OTHER'
        }
        
        # Mapowanie typów wydarzeń
        self.event_type_mapping = {
            'dywidendy': 'dividend',
            'wza': 'shareholder_meeting',
            'nwza': 'shareholder_meeting', 
            'zwza': 'shareholder_meeting',
            'wyniki spółek': 'earnings',
            'publikacja raportu': 'earnings',
            'rynek pierwotny': 'ipo',
            'dzień pierwszego notowania': 'ipo',
            'wycofanie': 'delisting',
            'inne': 'other'
        }
    
    def get_weekly_events(self, date: Optional[datetime] = None) -> List[CalendarEvent]:
        """
        Pobiera wydarzenia z kalendarza na dany tydzień
        
        Args:
            date: Data dla której pobrać kalendarz (domyślnie bieżąca)
            
        Returns:
            Lista wydarzeń kalendarzowych
        """
        if date is None:
            date = datetime.now()
            
        # Formatowanie daty do URL (format YYYY-MM-DD)
        date_str = date.strftime('%Y-%m-%d')
        url = f"{self.base_url}/{date_str}"
        
        logger.info(f"Pobieranie kalendarza z: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = self._parse_calendar_page(soup, url)
            
            logger.info(f"Znaleziono {len(events)} wydarzeń")
            return events
            
        except requests.RequestException as e:
            logger.error(f"Błąd pobierania kalendarza: {e}")
            return []
    
    def get_events_by_category(self, category: str, date: Optional[datetime] = None) -> List[CalendarEvent]:
        """
        Pobiera wydarzenia z konkretnej kategorii
        
        Args:
            category: Kategoria wydarzeń (dywidendy, wza, wyniki, rynek-pierwotny)
            date: Data dla której pobrać kalendarz
            
        Returns:
            Lista wydarzeń z danej kategorii
        """
        if date is None:
            date = datetime.now()
            
        date_str = date.strftime('%Y-%m-%d') 
        url = f"{self.base_url}/{date_str}?kategoria={category}"
        
        logger.info(f"Pobieranie kategorii {category} z: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = self._parse_calendar_page(soup, url)
            
            logger.info(f"Znaleziono {len(events)} wydarzeń w kategorii {category}")
            return events
            
        except requests.RequestException as e:
            logger.error(f"Błąd pobierania kategorii {category}: {e}")
            return []
    
    def _parse_calendar_page(self, soup: BeautifulSoup, source_url: str) -> List[CalendarEvent]:
        """
        Parsuje stronę kalendarza i wyodrębnia wydarzenia
        
        Args:
            soup: Obiekt BeautifulSoup ze stroną
            source_url: URL źródłowy strony
            
        Returns:
            Lista wydarzeń kalendarzowych
        """
        events = []
        
        try:
            # Wyszukiwanie wszystkich wydarzeń z klasą 'event'
            event_elements = soup.find_all('div', class_='event')
            logger.info(f"Znaleziono {len(event_elements)} elementów event")
            
            for event_element in event_elements:
                event = self._parse_event_element_new(event_element, source_url)
                if event:
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Błąd parsowania kalendarza: {e}")
        
        return events
    
    def _parse_event_element_new(self, event_element, source_url: str) -> Optional[CalendarEvent]:
        """
        Parsuje nowy format elementu wydarzenia z Bankier.pl
        """
        try:
            # Wyodrębnienie daty z elementu time
            time_element = event_element.find('time', class_='time')
            if not time_element:
                return None
                
            datetime_attr = time_element.get('datetime')
            if not datetime_attr:
                return None
                
            # Parsowanie daty
            event_date = datetime.strptime(datetime_attr, '%Y-%m-%d')
            
            # Wyodrębnienie symbolu spółki
            company_link = event_element.find('div', class_='company').find('a')
            if not company_link:
                return None
                
            href = company_link.get('href')
            if not href:
                return None
                
            symbol = self._extract_symbol_from_link(str(href))
            if not symbol:
                return None
            
            company_name = company_link.get_text().strip()
            
            # Wyodrębnienie kategorii wydarzenia
            category_element = event_element.find('div', class_='eventCategoryLabel')
            if not category_element:
                return None
                
            category_text = category_element.get_text().strip()
            
            # Wyodrębnienie opisu
            description_element = event_element.find('div', class_='eventDescription')
            description = ""
            if description_element:
                description_p = description_element.find('p')
                if description_p:
                    description = description_p.get_text().strip()
            
            # Klasyfikacja wydarzenia
            event_category, event_type = self._classify_event_from_category(category_text, description)
            
            # Określenie poziomu wpływu
            impact_level = self._determine_impact_level(event_category, description)
            
            return CalendarEvent(
                date=event_date,
                company_symbol=symbol,
                company_name=company_name,
                event_type=event_type,
                event_category=event_category,
                description=description,
                impact_level=impact_level,
                source_url=source_url
            )
            
        except Exception as e:
            logger.error(f"Błąd parsowania nowego formatu wydarzenia: {e}")
            return None
    
    def _classify_event_from_category(self, category_text: str, description: str) -> tuple[str, str]:
        """
        Klasyfikuje wydarzenie na podstawie kategorii z Bankier.pl
        """
        category_lower = category_text.lower()
        description_lower = description.lower()
        
        # Mapowanie kategorii Bankier.pl
        if 'dywidend' in category_lower:
            return 'DIVIDEND', 'dividend'
        elif 'wza' in category_lower:
            return 'SHAREHOLDER_MEETING', 'shareholder_meeting'
        elif 'wyniki' in category_lower or 'raport' in description_lower:
            return 'EARNINGS', 'earnings'
        elif 'pierwotny' in category_lower or 'ipo' in category_lower:
            return 'IPO', 'ipo'
        elif 'wycofanie' in description_lower:
            return 'DELISTING', 'delisting'
        else:
            return 'OTHER', 'other'
    
    def _parse_weekly_calendar(self, soup: BeautifulSoup, source_url: str) -> List[CalendarEvent]:
        """
        Parsuje kalendarz w formacie tygodniowym z Bankier.pl
        """
        events = []
        
        try:
            # Wyszukiwanie wszystkich linków do spółek
            company_links = soup.find_all('a', href=re.compile(r'/inwestowanie/profile/quote\.html\?symbol='))
            
            for link in company_links:
                try:
                    href = getattr(link, 'href', None) or (link.get('href') if hasattr(link, 'get') else None)
                    if not href:
                        continue
                        
                    symbol = self._extract_symbol_from_link(str(href))
                    if not symbol:
                        continue
                except Exception:
                    continue
                
                # Znalezienie kontenera z wydarzeniem
                event_container = link.find_parent()
                if not event_container:
                    continue
                
                # Wyodrębnienie informacji o wydarzeniu
                event_text = event_container.get_text().strip()
                event_date = self._find_date_for_event(link, soup)
                
                if event_date:
                    event = self._parse_event_text(symbol, event_text, event_date, source_url)
                    if event:
                        events.append(event)
                        
        except Exception as e:
            logger.error(f"Błąd parsowania kalendarza tygodniowego: {e}")
        
        return events
    
    def _extract_symbol_from_link(self, href: str) -> Optional[str]:
        """Wyodrębnia symbol spółki z linku"""
        if not href:
            return None
        match = re.search(r'symbol=([A-Z0-9]+)', href)
        return match.group(1) if match else None
    
    def _find_date_for_event(self, event_element, soup: BeautifulSoup) -> Optional[datetime]:
        """Znajduje datę wydarzenia na podstawie pozycji elementu"""
        
        # Wyszukiwanie poprzedzających nagłówków z datą
        current = event_element
        while current:
            if current.name in ['h2', 'h3', 'h4']:
                date_text = current.get_text().strip()
                if re.search(r'\d{1,2}\s+\w+', date_text):
                    return self._parse_polish_date(date_text)
            current = current.find_previous()
        
        return None
    
    def _parse_event_element(self, element, event_date: datetime, source_url: str) -> Optional[CalendarEvent]:
        """
        Parsuje pojedynczy element wydarzenia
        """
        try:
            text = element.get_text().strip()
            if not text:
                return None
            
            # Wyszukiwanie linku do spółki
            link = element.find('a', href=re.compile(r'symbol='))
            if not link:
                return None
            
            symbol = self._extract_symbol_from_link(link.get('href'))
            if not symbol:
                return None
            
            return self._parse_event_text(symbol, text, event_date, source_url)
            
        except Exception as e:
            logger.error(f"Błąd parsowania elementu wydarzenia: {e}")
            return None
    
    def _parse_event_text(self, symbol: str, text: str, event_date: datetime, source_url: str) -> Optional[CalendarEvent]:
        """
        Parsuje tekst wydarzenia i tworzy obiekt CalendarEvent
        """
        try:
            # Określenie typu i kategorii wydarzenia
            event_category, event_type = self._classify_event(text)
            
            # Określenie poziomu wpływu
            impact_level = self._determine_impact_level(event_category, text)
            
            # Wyodrębnienie nazwy spółki
            company_name = self._extract_company_name(text, symbol)
            
            return CalendarEvent(
                date=event_date,
                company_symbol=symbol,
                company_name=company_name,
                event_type=event_type,
                event_category=event_category,
                description=text.strip(),
                impact_level=impact_level,
                source_url=source_url
            )
            
        except Exception as e:
            logger.error(f"Błąd parsowania tekstu wydarzenia: {e}")
            return None
    
    def _classify_event(self, text: str) -> tuple[str, str]:
        """
        Klasyfikuje wydarzenie na podstawie tekstu
        
        Returns:
            Tuple (kategoria, typ)
        """
        text_lower = text.lower()
        
        # Dywidendy
        if any(word in text_lower for word in ['dywidend', 'wypłat', 'dzień ustalenia prawa']):
            return 'DIVIDEND', 'dividend'
        
        # WZA/NWZA
        if any(word in text_lower for word in ['wza', 'nwza', 'zwza', 'walny', 'nadzwyczajny']):
            return 'SHAREHOLDER_MEETING', 'shareholder_meeting'
        
        # Wyniki finansowe
        if any(word in text_lower for word in ['wyniki', 'raport', 'publikacja', 'półrocze', 'kwartał']):
            return 'EARNINGS', 'earnings'
        
        # Rynek pierwotny
        if any(word in text_lower for word in ['pierwsze notowanie', 'debiut', 'ipo', 'pierwszego notowania']):
            return 'IPO', 'ipo'
        
        # Wycofanie z giełdy
        if any(word in text_lower for word in ['wycofanie', 'delisting', 'zawieszenie']):
            return 'DELISTING', 'delisting'
        
        return 'OTHER', 'other'
    
    def _determine_impact_level(self, category: str, text: str) -> str:
        """
        Określa poziom wpływu wydarzenia na kurs
        """
        text_lower = text.lower()
        
        # Wysokie wyniki
        if category == 'EARNINGS':
            return 'HIGH'
        
        # Dywidendy - średni wpływ
        if category == 'DIVIDEND':
            # Wysokie dywidendy
            if re.search(r'(\d+[,.]?\d*)\s*zł', text_lower):
                return 'MEDIUM'
            return 'MEDIUM'
        
        # WZA - różny wpływ
        if category == 'SHAREHOLDER_MEETING':
            if any(word in text_lower for word in ['podział zysku', 'dywidend', 'fuzja', 'przejęcie']):
                return 'HIGH'
            return 'MEDIUM'
        
        # IPO - wysoki wpływ
        if category == 'IPO':
            return 'HIGH'
        
        # Wycofanie - bardzo wysoki wpływ
        if category == 'DELISTING':
            return 'VERY_HIGH'
        
        return 'LOW'
    
    def _extract_company_name(self, text: str, symbol: str) -> str:
        """Wyodrębnia nazwę spółki z tekstu lub zwraca symbol"""
        # W przypadku Bankier.pl często nazwa jest w linku
        # Na razie zwracamy symbol, można rozszerzyć
        return symbol
    
    def _parse_polish_date(self, date_text: str) -> Optional[datetime]:
        """
        Parsuje polską datę do obiektu datetime
        
        Args:
            date_text: Tekst daty w języku polskim, np. "21 lipca"
            
        Returns:
            Obiekt datetime lub None jeśli nie udało się sparsować
        """
        try:
            # Mapowanie polskich miesięcy
            polish_months = {
                'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4,
                'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8,
                'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12,
                'stycze': 1, 'luty': 2, 'marzec': 3, 'kwiecień': 4,
                'maj': 5, 'czerwiec': 6, 'lipiec': 7, 'sierpień': 8,
                'wrzesień': 9, 'październik': 10, 'listopad': 11, 'grudzień': 12
            }
            
            # Wyodrębnienie dnia i miesiąca
            match = re.search(r'(\d{1,2})\s+(\w+)', date_text.lower())
            if not match:
                return None
            
            day = int(match.group(1))
            month_name = match.group(2)
            
            # Znalezienie miesiąca
            month = None
            for pol_month, num in polish_months.items():
                if pol_month in month_name:
                    month = num
                    break
            
            if not month:
                return None
            
            # Obecny rok lub następny jeśli data już minęła
            current_year = datetime.now().year
            try:
                event_date = datetime(current_year, month, day)
                
                # Jeśli data jest z przeszłości, sprawdź czy nie chodzi o przyszły rok
                if event_date < datetime.now() - timedelta(days=7):
                    event_date = datetime(current_year + 1, month, day)
                
                return event_date
            except ValueError:
                return None
            
        except Exception as e:
            logger.error(f"Błąd parsowania daty '{date_text}': {e}")
            return None
    
    def save_events_to_database(self, events: List[CalendarEvent]) -> int:
        """
        Zapisuje wydarzenia do bazy danych
        
        Args:
            events: Lista wydarzeń do zapisania
            
        Returns:
            Liczba zapisanych wydarzeń
        """
        # Import Django models here after setup
        try:
            from apps.core.models import StockSymbol
            from news.models import CompanyCalendarEvent
        except ImportError:
            logger.error("Nie można zaimportować modeli Django")
            return 0
        
        saved_count = 0
        
        for event in events:
            try:
                # Znajdź lub utwórz symbol spółki
                stock_symbol, created = StockSymbol.objects.get_or_create(
                    symbol=event.company_symbol,
                    defaults={
                        'name': event.company_name,
                        'market': 'GPW',
                        'is_active': True
                    }
                )
                
                # Sprawdź czy wydarzenie już istnieje
                existing = CompanyCalendarEvent.objects.filter(
                    stock_symbol=stock_symbol,
                    event_date=event.date,
                    event_type=event.event_type,
                    description=event.description
                ).first()
                
                if not existing:
                    # Utwórz nowe wydarzenie
                    calendar_event = CompanyCalendarEvent.objects.create(
                        stock_symbol=stock_symbol,
                        event_date=event.date,
                        event_type=event.event_type,
                        event_category=event.event_category,
                        title=f"{event.company_symbol} - {event.event_category}",
                        description=event.description,
                        impact_level=event.impact_level,
                        source_url=event.source_url,
                        is_confirmed=True
                    )
                    
                    saved_count += 1
                    logger.info(f"Zapisano wydarzenie: {calendar_event}")
                else:
                    logger.debug(f"Wydarzenie już istnieje: {existing}")
                    
            except Exception as e:
                logger.error(f"Błąd zapisywania wydarzenia {event}: {e}")
        
        return saved_count
    
    def scrape_and_save_weekly_calendar(self, date: Optional[datetime] = None) -> Dict:
        """
        Kompletny proces scrapingu i zapisywania kalendarza tygodniowego
        
        Args:
            date: Data dla której pobrać kalendarz
            
        Returns:
            Słownik z wynikami operacji
        """
        logger.info("Rozpoczynam scraping kalendarza tygodniowego z Bankier.pl")
        
        if date is None:
            date = datetime.now()
        
        total_events = []
        
        # Pobierz wszystkie wydarzenia
        all_events = self.get_weekly_events(date)
        total_events.extend(all_events)
        
        # Opcjonalnie: pobierz wydarzenia z konkretnych kategorii
        for category in self.event_categories.keys():
            category_events = self.get_events_by_category(category, date)
            total_events.extend(category_events)
        
        # Usuń duplikaty
        unique_events = self._remove_duplicates(total_events)
        
        # Zapisz do bazy danych
        saved_count = self.save_events_to_database(unique_events)
        
        result = {
            'total_found': len(total_events),
            'unique_events': len(unique_events),
            'saved_count': saved_count,
            'date': date.strftime('%Y-%m-%d'),
            'source': 'bankier.pl'
        }
        
        logger.info(f"Scraping zakończony: {result}")
        return result
    
    def _remove_duplicates(self, events: List[CalendarEvent]) -> List[CalendarEvent]:
        """Usuwa duplikaty z listy wydarzeń"""
        seen = set()
        unique_events = []
        
        for event in events:
            # Klucz unikalności: symbol, data, typ, opis
            key = (event.company_symbol, event.date, event.event_type, event.description)
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
        
        return unique_events

def main():
    """Funkcja główna do testowania scrapera"""
    
    # Konfiguracja Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
    import django
    django.setup()
    
    scraper = BankierCalendarScraper()
    
    # Test scrapingu
    result = scraper.scrape_and_save_weekly_calendar()
    print(f"Wyniki scrapingu: {json.dumps(result, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    main()
