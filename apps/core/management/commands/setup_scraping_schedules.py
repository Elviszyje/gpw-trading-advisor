"""
Django management command to setup default scraping schedules
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.models import ScrapingSchedule
from datetime import time


class Command(BaseCommand):
    help = 'Setup default scraping schedules for different scraper types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing schedules and create new ones'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== Setting Up Default Scraping Schedules ===\n')
        )
        
        if options['reset']:
            count = ScrapingSchedule.objects.count()
            ScrapingSchedule.objects.all().delete()
            self.stdout.write(f"🗑️  Deleted {count} existing schedules\n")
        
        # Default schedules configuration
        default_schedules = [
            # News RSS - Every 30 minutes during market hours + 1h before market open
            {
                'name': 'News RSS - Market Hours',
                'scraper_type': 'news_rss',
                'frequency_value': 30,
                'frequency_unit': 'minutes',
                'active_hours_start': time(7, 0),  # 1h before market open
                'active_hours_end': time(18, 0),   # 30min after market close
                'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True, 'friday': True,
                'saturday': False, 'sunday': False,
                'scraper_config': {
                    'auto_analyze': True,  # Automatically analyze new articles
                    'max_articles_per_run': 20
                }
            },
            
            # News RSS - Off-hours (slower)
            {
                'name': 'News RSS - Off Hours',
                'scraper_type': 'news_rss',
                'frequency_value': 2,
                'frequency_unit': 'hours',
                'active_hours_start': time(18, 1),  # After market close
                'active_hours_end': time(6, 59),    # Before pre-market check
                'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True, 'friday': True,
                'saturday': True, 'sunday': True,
                'scraper_config': {
                    'auto_analyze': False,  # Don't auto-analyze off-hours
                    'max_articles_per_run': 10
                }
            },
            
            # Stock Prices - Every 5 minutes during market hours
            {
                'name': 'Stock Prices - Live Trading',
                'scraper_type': 'stock_prices',
                'frequency_value': 5,
                'frequency_unit': 'minutes',
                'active_hours_start': time(9, 0),   # Market open
                'active_hours_end': time(17, 30),   # Market close
                'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True, 'friday': True,
                'saturday': False, 'sunday': False,
                'scraper_config': {
                    'source': 'stooq',
                    'scrape_mode': 'all_monitored',  # Use database monitoring flags
                    'include_indices': True
                }
            },
            
            # Stock Prices - End of day
            {
                'name': 'Stock Prices - EOD Update',
                'scraper_type': 'stock_prices',
                'frequency_value': 1,
                'frequency_unit': 'days',
                'active_hours_start': time(18, 0),   # After market close
                'active_hours_end': time(19, 0),     # 1 hour window
                'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True, 'friday': True,
                'saturday': False, 'sunday': False,
                'scraper_config': {
                    'source': 'stooq',
                    'scrape_mode': 'all_monitored',  # Use database monitoring flags
                    'include_volume': True,
                    'include_historical': True
                }
            },
            
            # Calendar Events - Daily morning update
            {
                'name': 'Calendar Events - Daily',
                'scraper_type': 'calendar_events',
                'frequency_value': 1,
                'frequency_unit': 'days',
                'active_hours_start': time(7, 0),    # Early morning
                'active_hours_end': time(8, 0),      # Before market open
                'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True, 'friday': True,
                'saturday': False, 'sunday': False,
                'scraper_config': {
                    'event_types': ['earnings', 'dividends', 'shareholder_meetings'],
                    'days_ahead': 7  # Look 7 days ahead
                }
            },
            
            # ESPI Reports - Every 2 hours during business days
            {
                'name': 'ESPI Reports - Business Hours',
                'scraper_type': 'espi_reports',
                'frequency_value': 2,
                'frequency_unit': 'hours',
                'active_hours_start': time(8, 0),
                'active_hours_end': time(18, 0),
                'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True, 'friday': True,
                'saturday': False, 'sunday': False,
                'scraper_config': {
                    'report_types': ['current', 'periodic'],
                    'auto_classify': True
                }
            }
        ]
        
        created_count = 0
        
        for schedule_config in default_schedules:
            # Check if schedule already exists
            existing = ScrapingSchedule.objects.filter(
                name=schedule_config['name']
            ).first()
            
            if existing and not options['reset']:
                self.stdout.write(f"⚠️  Schedule '{schedule_config['name']}' already exists, skipping")
                continue
            
            # Create schedule
            schedule = ScrapingSchedule.objects.create(**schedule_config)
            schedule.calculate_next_run()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Created: {schedule.name}\n"
                    f"   Type: {schedule.scraper_type}\n"
                    f"   Frequency: {schedule.frequency_description}\n"
                    f"   Active: {', '.join(schedule.active_days)} "
                    f"{schedule.active_hours_start}-{schedule.active_hours_end}\n"
                    f"   Next run: {schedule.next_run}\n"
                )
            )
            
            created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 Setup complete! Created {created_count} schedules.\n"
                f"\nTo start the scheduler:\n"
                f"  python manage.py run_scheduled_scrapers\n"
                f"\nTo check status:\n"
                f"  python manage.py run_scheduled_scrapers --status\n"
                f"\nTo run in production, add to crontab:\n"
                f"  */5 * * * * cd /path/to/project && python manage.py run_scheduled_scrapers\n"
            )
        )
