"""
Scraping Scheduler Service - manages automated execution of scrapers
Supports both synchronous and asynchronous (Celery) execution modes
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.management import call_command
from django.conf import settings

from apps.core.models import ScrapingSchedule, ScrapingExecution
from apps.core.llm_service import LLMService

logger = logging.getLogger(__name__)


class ScrapingScheduler:
    """
    Service for managing automated scraping schedules
    Supports both sync and async execution modes
    """
    
    def __init__(self, use_celery: bool = True):
        self.llm_service = LLMService()
        self.use_celery = use_celery
        self.execute_scraper_task = None
        
        if use_celery:
            try:
                from celery import current_app
                from apps.core.tasks import execute_scraper_task
                
                # Test Celery connection
                current_app.control.inspect().active()
                self.execute_scraper_task = execute_scraper_task
                logger.info("Celery is available and will be used for parallel execution")
            except Exception as e:
                logger.warning(f"Celery not available, falling back to sync execution: {e}")
                self.use_celery = False
        
    def get_due_schedules(self) -> List[ScrapingSchedule]:
        """Get all schedules that are due to run"""
        due_schedules = []
        
        for schedule in ScrapingSchedule.objects.filter(is_active=True):
            if schedule.should_run_now():
                due_schedules.append(schedule)
                
        return due_schedules
    
    def execute_schedule(self, schedule: ScrapingSchedule, use_celery: Optional[bool] = None) -> ScrapingExecution:
        """Execute a specific scraping schedule"""
        
        # Allow override of instance setting
        use_celery_mode = use_celery if use_celery is not None else self.use_celery
        
        if use_celery_mode:
            return self._execute_schedule_async(schedule)
        else:
            return self._execute_schedule_sync(schedule)
    
    def _execute_schedule_async(self, schedule: ScrapingSchedule) -> ScrapingExecution:
        """Execute schedule using Celery (async)"""
        try:
            if not self.execute_scraper_task:
                raise Exception("Celery task not available")
            
            logger.info(f"Launching async execution of {schedule.name} ({schedule.scraper_type})")
            
            # Create execution record immediately
            execution = ScrapingExecution.objects.create(
                schedule=schedule,
                started_at=timezone.now()
            )
            
            # Launch Celery task
            task = self.execute_scraper_task.delay(schedule.pk)
            
            # Store task ID in execution details for tracking
            execution.execution_details = {
                'celery_task_id': task.id,
                'execution_mode': 'async',
                'launched_at': timezone.now().isoformat()
            }
            execution.save()
            
            logger.info(f"Async task {task.id} launched for {schedule.name}")
            
            return execution
            
        except Exception as e:
            logger.error(f"Failed to launch async task for {schedule.name}: {e}")
            # Fall back to sync execution
            logger.info(f"Falling back to sync execution for {schedule.name}")
            return self._execute_schedule_sync(schedule)
    
    def _execute_schedule_sync(self, schedule: ScrapingSchedule) -> ScrapingExecution:
        """Execute schedule synchronously (traditional way)"""
        # Create execution log
        execution = ScrapingExecution.objects.create(schedule=schedule, started_at=timezone.now())
        
        try:
            logger.info(f"Starting sync execution of {schedule.name} ({schedule.scraper_type})")
            
            # Execute based on scraper type
            if schedule.scraper_type == 'news_rss':
                result = self._execute_news_rss(schedule, execution)
            elif schedule.scraper_type == 'stock_prices':
                result = self._execute_stock_prices(schedule, execution)
            elif schedule.scraper_type == 'calendar_events':
                result = self._execute_calendar_events(schedule, execution)
            elif schedule.scraper_type == 'espi_reports':
                result = self._execute_espi_reports(schedule, execution)
            else:
                raise ValueError(f"Unknown scraper type: {schedule.scraper_type}")
            
            # Check if result contains error
            if result.get('error'):
                raise Exception(result['error'])
            
            # Update execution with results
            execution.success = True
            execution.items_processed = result.get('processed', 0)
            execution.items_created = result.get('created', 0)
            execution.items_updated = result.get('updated', 0)
            execution.execution_details = result
            execution.completed_at = timezone.now()
            execution.save()
            
            # Mark schedule as successfully executed
            schedule.mark_execution(success=True)
            
            logger.info(f"Successfully completed {schedule.name}: {result}")
            
        except Exception as e:
            logger.error(f"Error executing {schedule.name}: {str(e)}")
            
            execution.success = False
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()
            
            # Mark schedule as failed
            schedule.mark_execution(success=False)
            
        return execution

    def run_due_schedules_sync(self) -> List[ScrapingExecution]:
        """Run all due schedules synchronously (sequential)"""
        due_schedules = self.get_due_schedules()
        
        if not due_schedules:
            logger.info("No schedules due for execution")
            return []
        
        logger.info(f"Found {len(due_schedules)} schedules due for execution")
        executions = []
        
        for schedule in due_schedules:
            execution = self.execute_schedule(schedule, use_celery=False)
            executions.append(execution)
            
        return executions

    def run_due_schedules_async(self) -> List[ScrapingExecution]:
        """Run all due schedules asynchronously (parallel)"""
        if not self.use_celery or not self.execute_scraper_task:
            logger.warning("Celery not available, falling back to sync execution")
            return self.run_due_schedules_sync()
        
        try:
            from apps.core.tasks import run_due_schedules_parallel
            
            due_schedules = self.get_due_schedules()
            
            if not due_schedules:
                logger.info("No schedules due for execution")
                return []
            
            logger.info(f"Launching parallel execution of {len(due_schedules)} schedules")
            
            # Launch the parallel execution task
            task = run_due_schedules_parallel.delay()
            
            logger.info(f"Parallel execution task {task.id} launched")
            
            # Return empty list since executions are handled asynchronously
            return []
            
        except Exception as e:
            logger.error(f"Failed to launch parallel execution: {e}")
            logger.info("Falling back to sync execution")
            return self.run_due_schedules_sync()

    def run_due_schedules(self, use_async: Optional[bool] = None) -> List[ScrapingExecution]:
        """Run all due schedules - choose sync or async based on configuration"""
        use_async_mode = use_async if use_async is not None else self.use_celery
        
        if use_async_mode:
            return self.run_due_schedules_async()
        else:
            return self.run_due_schedules_sync()
            
    def _execute_news_rss(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict:
        """Execute RSS news scraping"""
        from django.core.management import call_command
        from io import StringIO
        import sys
        
        # Capture command output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Run the scraping command
            call_command('scrape_news')
            
            # Get output
            output = captured_output.getvalue()
            
            # Parse output for statistics (basic implementation)
            processed = 0
            created = 0
            
            # Simple parsing - could be enhanced
            if "articles processed" in output:
                # Extract numbers from output
                lines = output.split('\n')
                for line in lines:
                    if "processed" in line:
                        try:
                            processed = int(line.split()[0])
                        except:
                            pass
                    if "new articles" in line:
                        try:
                            created = int(line.split()[0])
                        except:
                            pass
            
            # Auto-analyze new articles if configured
            config = schedule.scraper_config
            if config.get('auto_analyze', False):
                self._auto_analyze_new_articles()
            
            return {
                'processed': processed,
                'created': created,
                'updated': 0,
                'output': output,
                'auto_analyzed': config.get('auto_analyze', False)
            }
            
        except Exception as e:
            logger.error(f"Error in news RSS scraping: {str(e)}")
            return {
                'processed': 0,
                'created': 0,
                'updated': 0,
                'output': captured_output.getvalue(),
                'error': str(e),
                'auto_analyzed': False
            }
            
        finally:
            sys.stdout = old_stdout
    
    def _execute_stock_prices(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict:
        """Execute stock prices scraping"""
        from django.core.management import call_command
        from io import StringIO
        import sys
        
        # Capture command output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Run the stock data collection command with --all flag
            call_command('collect_stock_data', '--all')
            
            # Get output
            output = captured_output.getvalue()
            
            # Parse output for statistics - improved parsing
            processed = 0
            created = 0
            successful = 0
            failed = 0
            
            # Parse the actual output format
            lines = output.split('\n')
            for line in lines:
                if "Data collection completed:" in line:
                    # Extract numbers from "36/36 successful"
                    try:
                        parts = line.split(':')[1].strip()  # "36/36 successful"
                        if '/' in parts:
                            successful = int(parts.split('/')[0])
                            processed = int(parts.split('/')[1].split()[0])
                    except:
                        pass
                elif "Successful:" in line and "stocks" in line:
                    # Extract from "• Successful: 36 stocks"
                    try:
                        parts = line.split(':')[1].strip()
                        if parts and parts[0].isdigit():
                            successful = int(parts.split()[0])
                    except:
                        pass
                elif "Failed:" in line and "stocks" in line:
                    # Extract from "• Failed: 0 stocks"
                    try:
                        parts = line.split(':')[1].strip()
                        if parts and parts[0].isdigit():
                            failed = int(parts.split()[0])
                    except:
                        pass
                elif "Created new data for" in line:
                    created += 1
            
            # If we couldn't parse, set reasonable defaults
            if processed == 0 and successful > 0:
                processed = successful
            if created == 0 and successful > 0:
                created = successful
            
            return {
                'processed': processed,
                'created': created,
                'updated': successful,
                'successful': successful,
                'failed': failed,
                'command_output': output[:500]  # Limit output size
            }
            
        except Exception as e:
            logger.error(f"Error in stock prices scraping: {str(e)}")
            return {
                'processed': 0,
                'created': 0,
                'updated': 0,
                'successful': 0,
                'failed': 0,
                'command_output': captured_output.getvalue()[:500],
                'error': str(e)
            }
            
        finally:
            sys.stdout = old_stdout
    
    def _execute_calendar_events(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict:
        """Execute calendar events scraping"""
        from django.core.management import call_command
        from io import StringIO
        import sys
        
        # Capture command output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Run the calendar scraping command
            call_command('scrape_bankier_calendar')
            
            # Get output
            output = captured_output.getvalue()
            
            # Parse output for statistics
            processed = 0
            created = 0
            
            if "events" in output or "processed" in output:
                lines = output.split('\n')
                for line in lines:
                    if "events" in line or "processed" in line:
                        try:
                            numbers = [int(s) for s in line.split() if s.isdigit()]
                            if numbers:
                                processed = numbers[0]
                        except:
                            pass
            
            return {
                'processed': processed,
                'created': created,
                'updated': 0,
                'command_output': output[:500]
            }
            
        except Exception as e:
            logger.error(f"Error in calendar events scraping: {str(e)}")
            return {
                'processed': 0,
                'created': 0,
                'updated': 0,
                'command_output': captured_output.getvalue()[:500],
                'error': str(e)
            }
            
        finally:
            sys.stdout = old_stdout
    
    def _execute_espi_reports(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict:
        """Execute ESPI reports scraping"""
        # ESPI reports - mock implementation for now
        # Would need actual ESPI scraping command
        
        config = schedule.scraper_config
        report_types = config.get('report_types', ['current', 'periodic'])
        
        logger.info(f"Fetching ESPI reports: {report_types}")
        
        # Mock implementation - would be replaced with actual scraping
        processed = 3
        created = 2
        
        return {
            'processed': processed,
            'created': created,
            'updated': 0,
            'report_types': report_types
        }
    
    def _auto_analyze_new_articles(self):
        """Automatically analyze new articles with AI"""
        from apps.news.models import NewsArticleModel
        
        # Get unanalyzed articles
        unanalyzed = NewsArticleModel.objects.filter(
            ai_classification__isnull=True
        )[:5]  # Limit to 5 for performance
        
        if unanalyzed:
            logger.info(f"Auto-analyzing {len(unanalyzed)} new articles")
            
            for article in unanalyzed:
                try:
                    classification = self.llm_service.analyze_news_article(article)
                    if classification:
                        logger.info(f"Analyzed: {article.title[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to analyze article {article.pk}: {e}")

    def get_schedule_status(self) -> Dict:
        """Get overview of all schedules and their status"""
        schedules = ScrapingSchedule.objects.all()
        
        status = {
            'total_schedules': schedules.count(),
            'active_schedules': schedules.filter(is_active=True).count(),
            'due_now': len(self.get_due_schedules()),
            'schedules': []
        }
        
        for schedule in schedules:
            schedule_info = {
                'id': schedule.pk,
                'name': schedule.name,
                'type': schedule.scraper_type,
                'is_active': schedule.is_active,
                'frequency': schedule.frequency_description,
                'active_days': schedule.active_days,
                'active_hours': f"{schedule.active_hours_start} - {schedule.active_hours_end}",
                'last_run': schedule.last_run,
                'last_success': schedule.last_success,
                'next_run': schedule.next_run,
                'failure_count': schedule.failure_count,
                'should_run_now': schedule.should_run_now()
            }
            status['schedules'].append(schedule_info)
        
        return status


# Convenience function
def run_scheduled_scrapers():
    """Convenience function to run all due scrapers"""
    scheduler = ScrapingScheduler()
    return scheduler.run_due_schedules()
