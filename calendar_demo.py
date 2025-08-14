"""
Demonstracja systemu kalendarza wydarzeń korporacyjnych.
Pokazuje jak działa pobieranie i przetwarzanie wydarzeń z różnych źródeł.
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django environment
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.scrapers.calendar_espi_scraper import CompanyCalendarScraper, CalendarEvent
from apps.scrapers.models import CompanyCalendarEvent
from apps.core.models import StockSymbol


def create_sample_calendar_events():
    """Create sample calendar events to demonstrate the system."""
    print("🗓️  CREATING SAMPLE CALENDAR EVENTS")
    print("=" * 60)
    
    # Get a sample stock
    try:
        pkn_stock = StockSymbol.objects.get(symbol='PKN')
    except StockSymbol.DoesNotExist:
        print("❌ PKN stock not found in database")
        return
    
    # Sample events that might appear in a real calendar
    sample_events = [
        {
            'title': 'Publikacja wyników finansowych Q4 2024',
            'event_type': 'earnings',
            'description': 'Publikacja raportu rocznego PKN ORLEN za rok 2024',
            'event_date': datetime.now() + timedelta(days=7),
            'impact_level': 'high',
            'source_url': 'https://www.orlen.pl/pl/relacje-inwestorskie',
        },
        {
            'title': 'Walne Zgromadzenie Akcjonariuszy',
            'event_type': 'agm',
            'description': 'Zwyczajne Walne Zgromadzenie Akcjonariuszy PKN ORLEN',
            'event_date': datetime.now() + timedelta(days=21),
            'impact_level': 'medium',
            'source_url': 'https://www.orlen.pl/pl/relacje-inwestorskie',
        },
        {
            'title': 'Dzień dywidendy',
            'event_type': 'dividend',
            'description': 'Dzień ustalenia prawa do dywidendy za rok 2024',
            'event_date': datetime.now() + timedelta(days=35),
            'impact_level': 'high',
            'source_url': 'https://www.orlen.pl/pl/relacje-inwestorskie',
        },
        {
            'title': 'Konferencja wyników Q1 2025',
            'event_type': 'conference',
            'description': 'Telekonferencja z zarządem dot. wyników Q1 2025',
            'event_date': datetime.now() + timedelta(days=45),
            'impact_level': 'medium',
            'source_url': 'https://www.orlen.pl/pl/relacje-inwestorskie',
        },
    ]
    
    created_count = 0
    
    for event_data in sample_events:
        # Check if event already exists
        existing = CompanyCalendarEvent.objects.filter(
            stock_symbol=pkn_stock,
            title=event_data['title']
        ).first()
        
        if not existing:
            event = CompanyCalendarEvent(
                stock_symbol=pkn_stock,
                event_type=event_data['event_type'],
                title=event_data['title'],
                description=event_data['description'],
                event_date=event_data['event_date'],
                impact_level=event_data['impact_level'],
                source_url=event_data['source_url'],
                is_confirmed=True
            )
            event.save()
            created_count += 1
            
            print(f"✅ Created: {event_data['title']}")
            print(f"   📅 Date: {event_data['event_date'].strftime('%Y-%m-%d')}")
            print(f"   📊 Impact: {event_data['impact_level']}")
            print(f"   🏷️  Type: {event_data['event_type']}")
            print()
    
    print(f"📈 Created {created_count} new calendar events")
    return created_count


def demonstrate_calendar_filtering():
    """Demonstrate calendar event filtering and analysis."""
    print("\n🔍 CALENDAR EVENT ANALYSIS")
    print("=" * 60)
    
    # Get all events
    all_events = CompanyCalendarEvent.objects.all()
    print(f"📊 Total events in database: {all_events.count()}")
    
    # Filter by impact level
    high_impact = CompanyCalendarEvent.objects.filter(impact_level='high')
    print(f"🔴 High impact events: {high_impact.count()}")
    
    # Filter by event type
    earnings_events = CompanyCalendarEvent.objects.filter(event_type='earnings')
    dividend_events = CompanyCalendarEvent.objects.filter(event_type='dividend')
    agm_events = CompanyCalendarEvent.objects.filter(event_type='agm')
    
    print(f"💰 Earnings events: {earnings_events.count()}")
    print(f"💵 Dividend events: {dividend_events.count()}")
    print(f"🏛️  AGM events: {agm_events.count()}")
    
    # Upcoming events (next 30 days)
    upcoming = CompanyCalendarEvent.objects.filter(
        event_date__gte=datetime.now(),
        event_date__lte=datetime.now() + timedelta(days=30)
    ).order_by('event_date')
    
    print(f"\n📅 UPCOMING EVENTS (Next 30 days): {upcoming.count()}")
    print("-" * 40)
    
    for event in upcoming:
        days_until = (event.event_date.date() - datetime.now().date()).days
        impact_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(event.impact_level, '⚪')
        
        print(f"{impact_emoji} {event.title}")
        print(f"   📅 {event.event_date.strftime('%Y-%m-%d')} (in {days_until} days)")
        print(f"   🏢 {event.stock_symbol.symbol} - {event.event_type}")
        print()


def demonstrate_calendar_scraper_logic():
    """Demonstrate how the calendar scraper logic works."""
    print("\n🔧 CALENDAR SCRAPER LOGIC DEMO")
    print("=" * 60)
    
    scraper = CompanyCalendarScraper()
    
    # Show scraper configuration
    print("📋 Calendar Sources Configuration:")
    for source_name, config in scraper.calendar_sources.items():
        print(f"  🌐 {source_name}:")
        print(f"     Base URL: {config['base_url']}")
        print(f"     Calendar URL: {config.get('calendar_url', 'N/A')}")
        print()
    
    # Demonstrate event classification
    print("🏷️  EVENT TYPE CLASSIFICATION:")
    
    sample_titles = [
        "Publikacja wyników finansowych Q4 2024",
        "Walne Zgromadzenie Akcjonariuszy",
        "Dzień dywidendy za rok 2024",
        "Konferencja prasowa zarządu",
        "Podział akcji w stosunku 1:2",
        "Przejęcie spółki XYZ",
    ]
    
    for title in sample_titles:
        event_type = scraper._classify_event_type(title, "")
        impact_level = scraper._determine_impact_level(event_type, title)
        
        print(f"  📝 '{title}'")
        print(f"     Type: {event_type} | Impact: {impact_level}")
        print()


def show_real_world_integration():
    """Show how this would integrate with real data sources."""
    print("\n🌍 REAL-WORLD INTEGRATION EXAMPLES")
    print("=" * 60)
    
    print("📡 Potential Data Sources for Calendar Events:")
    print()
    
    sources = [
        {
            'name': 'GPW Infostrefa',
            'url': 'https://infostrefa.com/pl/kalendarz-gpw',
            'description': 'Official GPW calendar with corporate events',
            'data_types': ['earnings', 'agm', 'dividend', 'conferences']
        },
        {
            'name': 'Stooq Calendar',
            'url': 'https://stooq.pl/kalendarz/',
            'description': 'Financial calendar with earnings dates',
            'data_types': ['earnings', 'economic_data']
        },
        {
            'name': 'Company IR Pages',
            'url': 'Various company websites',
            'description': 'Direct from investor relations pages',
            'data_types': ['all_types']
        },
        {
            'name': 'Bloomberg/Reuters APIs',
            'url': 'Premium data feeds',
            'description': 'Professional financial data',
            'data_types': ['comprehensive']
        }
    ]
    
    for source in sources:
        print(f"🔗 {source['name']}")
        print(f"   URL: {source['url']}")
        print(f"   📄 {source['description']}")
        print(f"   📊 Data: {', '.join(source['data_types'])}")
        print()
    
    print("⚙️  IMPLEMENTATION STRATEGY:")
    print("1. Start with GPW official sources (most reliable)")
    print("2. Add stooq.pl integration (already working)")
    print("3. Scrape major company IR pages")
    print("4. Integrate premium APIs for comprehensive coverage")
    print("5. Add ML-based event classification and impact prediction")


def main():
    """Run the calendar demonstration."""
    print("🗓️  GPW CALENDAR SYSTEM DEMONSTRATION")
    print("=" * 80)
    
    # Step 1: Create sample events
    create_sample_calendar_events()
    
    # Step 2: Analyze events
    demonstrate_calendar_filtering()
    
    # Step 3: Show scraper logic
    demonstrate_calendar_scraper_logic()
    
    # Step 4: Show integration possibilities
    show_real_world_integration()
    
    print("\n✅ CALENDAR DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
