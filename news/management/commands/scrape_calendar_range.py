"""
Django Management Command for Enhanced Calendar Scraping
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, date, timedelta
import logging

from news.models import CalendarScrapingJob
from scrapers.bankier_calendar_scraper import BankierCalendarScraper


User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape calendar events with date range support and change tracking'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)',
            default=date.today().strftime('%Y-%m-%d')
        )
        
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)',
            default=(date.today() + timedelta(weeks=12)).strftime('%Y-%m-%d')
        )
        
        parser.add_argument(
            '--weeks-ahead',
            type=int,
            help='Number of weeks ahead to scrape (alternative to end-date)',
            default=None
        )
        
        parser.add_argument(
            '--job-name',
            type=str,
            help='Name for the scraping job',
            default=None
        )
        
        parser.add_argument(
            '--rate-limit',
            type=float,
            help='Seconds to wait between requests',
            default=1.0
        )
        
        parser.add_argument(
            '--create-job',
            action='store_true',
            help='Create a CalendarScrapingJob record to track progress'
        )
    
    def handle(self, *args, **options):
        # Parse dates
        try:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f"Invalid start date format: {options['start_date']}")
        
        if options['weeks_ahead']:
            end_date = start_date + timedelta(weeks=options['weeks_ahead'])
        else:
            try:
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f"Invalid end date format: {options['end_date']}")
        
        # Validate date range
        if start_date >= end_date:
            raise CommandError("End date must be after start date")
        
        if (end_date - start_date).days > 365:
            raise CommandError("Date range cannot exceed 1 year")
        
        # Create job if requested
        job = None
        if options['create_job']:
            job_name = options['job_name'] or f"Calendar Scrape {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Get or create admin user for job
            admin_user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@localhost',
                    'is_staff': True,
                    'is_superuser': True
                }
            )
            
            job = CalendarScrapingJob.objects.create(
                name=job_name,
                description=f"Scraping calendar events from {start_date} to {end_date}",
                start_date=start_date,
                end_date=end_date,
                source_urls=['https://www.bankier.pl/gielda/kalendarium/'],
                created_by=admin_user
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Created scraping job: {job.name} (ID: {job.id})')
            )
        
        # Initialize scraper
        scraper = BankierCalendarScraper(rate_limit=options['rate_limit'])
        
        # Start scraping
        self.stdout.write(f'Starting calendar scrape from {start_date} to {end_date}...')
        
        try:
            result = scraper.scrape_calendar_range(start_date, end_date)
            
            # Display results
            if result.get('success', False):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Scraping completed successfully!\n"
                        f"📊 Events found: {result.get('events_found', 0)}\n"
                        f"🆕 Events created: {result.get('events_created', 0)}\n"
                        f"🔄 Events updated: {result.get('events_updated', 0)}\n"
                        f"⚠️ Date changes detected: {result.get('date_changes_detected', 0)}\n"
                        f"📅 Date range: {result.get('date_range', 'N/A')}"
                    )
                )
                
                if result.get('errors'):
                    self.stdout.write(
                        self.style.WARNING(f"⚠️ Errors encountered: {len(result['errors'])}")
                    )
                    for error in result['errors'][:5]:  # Show first 5 errors
                        self.stdout.write(f"  - {error}")
                
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Scraping failed: {result.get('error', 'Unknown error')}"
                    )
                )
                
                if result.get('partial_results'):
                    self.stdout.write(
                        f"📊 Partial results:\n"
                        f"🆕 Events created: {result.get('events_created', 0)}\n"
                        f"🔄 Events updated: {result.get('events_updated', 0)}"
                    )
        
        except Exception as e:
            error_msg = f"Critical error during scraping: {str(e)}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            logger.error(error_msg, exc_info=True)
            
            if job:
                job.status = 'failed'
                job.error_message = error_msg
                job.completed_at = timezone.now()
                job.save()
            
            raise CommandError(error_msg)
        
        # Final job update
        if job:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Job completed: {job.name}')
            )
            self.stdout.write(f'📝 View job details: /admin/news/calendarscrapingjob/{job.id}/')
        
        self.stdout.write(
            self.style.SUCCESS('🎉 Calendar scraping completed!')
        )
