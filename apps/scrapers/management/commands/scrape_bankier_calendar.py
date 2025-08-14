"""
Django management command do uruchomienia scrapera Bankier.pl
"""

from django.core.management.base import BaseCommand
from datetime import datetime
import json
import sys
import os

# Dodaj scraper do ścieżki
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from scraper.calendar.bankier_calendar_scraper import BankierCalendarScraper
from apps.core.models import StockSymbol
from apps.scrapers.models import CompanyCalendarEvent


class Command(BaseCommand):
    help = 'Uruchamia scraper kalendarza Bankier.pl'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Data w formacie YYYY-MM-DD (domyślnie dzisiaj)',
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Tylko pobierz dane bez zapisywania do bazy',
        )
    
    def handle(self, *args, **options):
        self.stdout.write("=== SCRAPER KALENDARZA BANKIER.PL ===")
        
        # Parse date
        date = None
        if options['date']:
            try:
                date = datetime.strptime(options['date'], '%Y-%m-%d')
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"Nieprawidłowy format daty: {options['date']}")
                )
                return
        
        scraper = BankierCalendarScraper()
        
        # Pobierz wydarzenia
        events = scraper.get_weekly_events(date)
        
        self.stdout.write(f"Znaleziono {len(events)} wydarzeń z Bankier.pl")
        
        # Wyświetl przykładowe wydarzenia
        self.stdout.write("\n=== PRZYKŁADOWE WYDARZENIA ===")
        for i, event in enumerate(events[:10]):
            self.stdout.write(f"{i+1}. {event.company_symbol} - {event.event_category}")
            self.stdout.write(f"   Data: {event.date.strftime('%Y-%m-%d')}")
            self.stdout.write(f"   Opis: {event.description}")
            self.stdout.write(f"   Wpływ: {event.impact_level}")
            self.stdout.write("")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("Dry run - nie zapisuję do bazy"))
            return
        
        # Zapisz do bazy danych
        self.stdout.write("=== ZAPISYWANIE DO BAZY DANYCH ===")
        saved_count = 0
        errors = 0
        
        for event in events:
            try:
                # Znajdź lub utwórz symbol spółki
                stock_symbol, created = StockSymbol.objects.get_or_create(
                    symbol=event.company_symbol,
                    defaults={
                        'name': event.company_name,
                        'is_monitored': True
                    }
                )
                
                if created:
                    self.stdout.write(f"Utworzono nowy symbol: {stock_symbol}")
                
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
                        title=f"{event.company_symbol} - {event.event_category}",
                        description=event.description,
                        impact_level=event.impact_level.lower(),
                        is_confirmed=True
                    )
                    
                    saved_count += 1
                    self.stdout.write(f"✓ Zapisano: {calendar_event}")
                else:
                    self.stdout.write(f"⚠ Istnieje: {existing}")
                    
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Błąd zapisywania {event.company_symbol}: {e}")
                )
        
        self.stdout.write(f"\n=== PODSUMOWANIE ===")
        self.stdout.write(f"Pobrano: {len(events)} wydarzeń")
        self.stdout.write(f"Zapisano: {saved_count} nowych wydarzeń")
        self.stdout.write(f"Błędów: {errors}")
        
        # Sprawdź co jest w bazie
        total_events = CompanyCalendarEvent.objects.count()
        self.stdout.write(f"Łącznie w bazie: {total_events} wydarzeń")
        
        # Wyświetl wydarzenia z bazy dla weryfikacji
        self.stdout.write(f"\n=== WYDARZENIA Z BAZY DANYCH (NAJNOWSZE) ===")
        recent_events = CompanyCalendarEvent.objects.order_by('-created_at')[:5]
        
        for event in recent_events:
            self.stdout.write(f"• {event.stock_symbol.symbol} - {event.event_type}")
            self.stdout.write(f"  Data: {event.event_date}")
            self.stdout.write(f"  Opis: {event.description}")
            self.stdout.write(f"  Wpływ: {event.impact_level}")
            self.stdout.write("")
            
        self.stdout.write(self.style.SUCCESS("Scraping zakończony!"))
