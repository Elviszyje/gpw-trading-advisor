#!/usr/bin/env python
"""
Skrypt do uruchomienia scrapera kalendarza Bankier.pl z Django
"""

import os
import sys
import django
from datetime import datetime
import json

# Konfiguracja Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

# Teraz możemy importować scraper i modele
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')

from scraper.calendar.bankier_calendar_scraper import BankierCalendarScraper
from apps.core.models import StockSymbol
from news.models import CompanyCalendarEvent

def run_bankier_scraper():
    """Uruchamia scraper kalendarza Bankier.pl"""
    print("=== SCRAPER KALENDARZA BANKIER.PL ===")
    
    scraper = BankierCalendarScraper()
    
    # Pobierz wydarzenia
    events = scraper.get_weekly_events()
    
    print(f"Znaleziono {len(events)} wydarzeń z Bankier.pl")
    
    # Wyświetl przykładowe wydarzenia
    print("\n=== PRZYKŁADOWE WYDARZENIA ===")
    for i, event in enumerate(events[:10]):
        print(f"{i+1}. {event.company_symbol} - {event.event_category}")
        print(f"   Data: {event.date.strftime('%Y-%m-%d')}")
        print(f"   Opis: {event.description}")
        print(f"   Wpływ: {event.impact_level}")
        print()
    
    # Zapisz do bazy danych
    print("=== ZAPISYWANIE DO BAZY DANYCH ===")
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
            
            if created:
                print(f"Utworzono nowy symbol: {stock_symbol}")
            
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
                print(f"✓ Zapisano: {calendar_event}")
            else:
                print(f"⚠ Istnieje: {existing}")
                
        except Exception as e:
            print(f"✗ Błąd zapisywania {event.company_symbol}: {e}")
    
    print(f"\n=== PODSUMOWANIE ===")
    print(f"Pobrano: {len(events)} wydarzeń")
    print(f"Zapisano: {saved_count} nowych wydarzeń")
    
    # Sprawdź co jest w bazie
    total_events = CompanyCalendarEvent.objects.count()
    print(f"Łącznie w bazie: {total_events} wydarzeń")
    
    # Wyświetl wydarzenia z bazy dla weryfikacji
    print(f"\n=== WYDARZENIA Z BAZY DANYCH ===")
    recent_events = CompanyCalendarEvent.objects.order_by('-created_at')[:10]
    
    for event in recent_events:
        print(f"• {event.stock_symbol.symbol} - {event.event_category}")
        print(f"  Data: {event.event_date}")
        print(f"  Opis: {event.description}")
        print(f"  Wpływ: {event.impact_level}")
        print()

if __name__ == "__main__":
    run_bankier_scraper()
