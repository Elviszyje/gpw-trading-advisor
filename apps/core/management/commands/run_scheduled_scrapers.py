"""
Django management command for running scheduled scrapers
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.scheduler_service import ScrapingScheduler
from apps.core.models import ScrapingSchedule, ScrapingExecution
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run scheduled scraping tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check which schedules are due, do not execute'
        )
        parser.add_argument(
            '--schedule-id',
            type=int,
            help='Run specific schedule by ID'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['news_rss', 'stock_prices', 'calendar_events', 'espi_reports'],
            help='Run all schedules of specific type'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show status of all schedules'
        )

    def handle(self, *args, **options):
        scheduler = ScrapingScheduler()
        
        if options['status']:
            self.show_schedule_status(scheduler)
            return
        
        if options['check_only']:
            self.check_due_schedules(scheduler)
            return
            
        if options['schedule_id']:
            self.run_specific_schedule(options['schedule_id'], scheduler)
            return
            
        if options['type']:
            self.run_schedules_by_type(options['type'], scheduler)
            return
        
        # Default: run all due schedules
        self.run_all_due_schedules(scheduler)
    
    def show_schedule_status(self, scheduler):
        """Show status of all schedules"""
        self.stdout.write(
            self.style.SUCCESS('=== Scraping Schedules Status ===\n')
        )
        
        status = scheduler.get_schedule_status()
        
        self.stdout.write(f"📊 Total schedules: {status['total_schedules']}")
        self.stdout.write(f"✅ Active schedules: {status['active_schedules']}")
        self.stdout.write(f"⏰ Due now: {status['due_now']}")
        self.stdout.write("")
        
        for schedule_info in status['schedules']:
            status_icon = "🟢" if schedule_info['is_active'] else "🔴"
            due_icon = "⚡" if schedule_info['should_run_now'] else "⏳"
            
            self.stdout.write(f"{status_icon} {due_icon} {schedule_info['name']}")
            self.stdout.write(f"    Type: {schedule_info['type']}")
            self.stdout.write(f"    Frequency: {schedule_info['frequency']}")
            self.stdout.write(f"    Active: {', '.join(schedule_info['active_days'])} {schedule_info['active_hours']}")
            
            if schedule_info['last_success']:
                self.stdout.write(f"    Last success: {schedule_info['last_success'].strftime('%Y-%m-%d %H:%M')}")
            else:
                self.stdout.write(f"    Last success: Never")
                
            if schedule_info['next_run']:
                self.stdout.write(f"    Next run: {schedule_info['next_run'].strftime('%Y-%m-%d %H:%M')}")
                
            if schedule_info['failure_count'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"    ⚠️  Failures: {schedule_info['failure_count']}")
                )
            
            self.stdout.write("")
    
    def check_due_schedules(self, scheduler):
        """Check which schedules are due without executing"""
        self.stdout.write(
            self.style.SUCCESS('=== Checking Due Schedules ===\n')
        )
        
        due_schedules = scheduler.get_due_schedules()
        
        if not due_schedules:
            self.stdout.write("✅ No schedules are currently due")
            return
        
        self.stdout.write(f"⏰ Found {len(due_schedules)} schedules due for execution:\n")
        
        for schedule in due_schedules:
            self.stdout.write(f"• {schedule.name} ({schedule.get_scraper_type_display()})")
            self.stdout.write(f"  Frequency: {schedule.frequency_description}")
            self.stdout.write(f"  Last run: {schedule.last_run or 'Never'}")
            self.stdout.write("")
    
    def run_specific_schedule(self, schedule_id, scheduler):
        """Run a specific schedule by ID"""
        try:
            schedule = ScrapingSchedule.objects.get(id=schedule_id)
        except ScrapingSchedule.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Schedule with ID {schedule_id} not found')
            )
            return
        
        self.stdout.write(f"🚀 Running schedule: {schedule.name}")
        
        execution = scheduler.execute_schedule(schedule)
        
        if execution.success:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Successfully completed {schedule.name}\n"
                    f"   Processed: {execution.items_processed}\n"
                    f"   Created: {execution.items_created}\n"
                    f"   Updated: {execution.items_updated}"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Failed to execute {schedule.name}\n"
                    f"   Error: {execution.error_message}"
                )
            )
    
    def run_schedules_by_type(self, scraper_type, scheduler):
        """Run all active schedules of specific type"""
        schedules = ScrapingSchedule.objects.filter(
            scraper_type=scraper_type,
            is_active=True
        )
        
        if not schedules:
            self.stdout.write(f"No active schedules found for type: {scraper_type}")
            return
        
        self.stdout.write(f"🚀 Running {len(schedules)} schedules of type: {scraper_type}\n")
        
        success_count = 0
        error_count = 0
        
        for schedule in schedules:
            self.stdout.write(f"Running: {schedule.name}...")
            
            execution = scheduler.execute_schedule(schedule)
            
            if execution.success:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Success - Processed: {execution.items_processed}, "
                        f"Created: {execution.items_created}"
                    )
                )
                success_count += 1
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Failed - {execution.error_message}")
                )
                error_count += 1
        
        self.stdout.write(f"\n📊 Summary: {success_count} succeeded, {error_count} failed")
    
    def run_all_due_schedules(self, scheduler):
        """Run all schedules that are due"""
        self.stdout.write(
            self.style.SUCCESS('=== Running Scheduled Scrapers ===\n')
        )
        
        executions = scheduler.run_due_schedules()
        
        if not executions:
            self.stdout.write("✅ No schedules were due for execution")
            return
        
        success_count = 0
        error_count = 0
        
        self.stdout.write(f"🚀 Executed {len(executions)} schedules:\n")
        
        for execution in executions:
            if execution.success:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ {execution.schedule.name} - "
                        f"Processed: {execution.items_processed}, "
                        f"Created: {execution.items_created}"
                    )
                )
                success_count += 1
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ {execution.schedule.name} - {execution.error_message}"
                    )
                )
                error_count += 1
        
        self.stdout.write(f"\n📊 Summary: {success_count} succeeded, {error_count} failed")
        
        # Show next scheduled runs
        self.stdout.write("\n⏰ Next scheduled runs:")
        upcoming = ScrapingSchedule.objects.filter(
            is_active=True,
            next_run__isnull=False
        ).order_by('next_run')[:5]
        
        for schedule in upcoming:
            next_run_str = schedule.next_run.strftime('%Y-%m-%d %H:%M') if schedule.next_run else 'Not scheduled'
            self.stdout.write(
                f"  • {schedule.name}: {next_run_str}"
            )
