"""
Scraping Scheduler Service - manages automated execution of scrapers
Supports both synchronous and asynchronous (Celery) execution modes
"""

import logging
from typing import Dict, List, Optional, Any
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
        self.celery_available = False
        self.execute_scraper_task = None
        self.run_due_schedules_parallel = None
        
        if use_celery:
            try:
                # Try to import Celery
                from celery import current_app as celery_app
                
                # Test Celery connection with a simple check
                try:
                    inspector = celery_app.control.inspect()
                    if inspector is not None:
                        self.celery_available = True
                        logger.info("Celery is available and will be used for parallel execution")
                        
                        # Import tasks if available
                        try:
                            from apps.core.tasks import execute_scraper_task, run_due_schedules_parallel
                            self.execute_scraper_task = execute_scraper_task
                            self.run_due_schedules_parallel = run_due_schedules_parallel
                        except ImportError as e:
                            logger.warning(f"Celery tasks not available: {e}")
                            self.celery_available = False
                    else:
                        logger.warning("Celery inspector is None, falling back to sync execution")
                        self.use_celery = False
                except Exception as e:
                    logger.warning(f"Celery not properly configured, falling back to sync execution: {e}")
                    self.use_celery = False
                    
            except ImportError:
                logger.warning("Celery not installed, falling back to sync execution")
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
        use_celery_mode = use_celery if use_celery is not None else (self.use_celery and self.celery_available)
        
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
            task_result = self.execute_scraper_task.delay(schedule.pk)
            
            # Store task ID in execution details for tracking
            execution.execution_details = {
                'celery_task_id': str(task_result.id),
                'execution_mode': 'async',
                'launched_at': timezone.now().isoformat()
            }
            execution.save()
            
            logger.info(f"Async task {task_result.id} launched for {schedule.name}")
            
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
        if not self.celery_available or not self.run_due_schedules_parallel:
            logger.warning("Celery not available, falling back to sync execution")
            return self.run_due_schedules_sync()
        
        try:
            due_schedules = self.get_due_schedules()
            
            if not due_schedules:
                logger.info("No schedules due for execution")
                return []
            
            logger.info(f"Launching parallel execution of {len(due_schedules)} schedules")
            
            # Launch the parallel execution task
            task_result = self.run_due_schedules_parallel.delay()
            
            logger.info(f"Parallel execution task {task_result.id} launched")
            
            # Return empty list since executions are handled asynchronously
            return []
            
        except Exception as e:
            logger.error(f"Failed to launch parallel execution: {e}")
            logger.info("Falling back to sync execution")
            return self.run_due_schedules_sync()

    def run_due_schedules(self, use_async: Optional[bool] = None) -> List[ScrapingExecution]:
        """Run all due schedules - choose sync or async based on configuration"""
        use_async_mode = use_async if use_async is not None else (self.use_celery and self.celery_available)
        
        if use_async_mode:
            return self.run_due_schedules_async()
        else:
            return self.run_due_schedules_sync()
            
    def _execute_news_rss(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict[str, Any]:
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
            
            # Parse output to get statistics
            output = captured_output.getvalue()
            
            # Simple parsing - looking for patterns like "Created X articles"
            created = 0
            updated = 0
            for line in output.split('\n'):
                if 'Created' in line and 'articles' in line:
                    try:
                        created = int(line.split()[1])
                    except (IndexError, ValueError):
                        pass
                elif 'Updated' in line and 'articles' in line:
                    try:
                        updated = int(line.split()[1])
                    except (IndexError, ValueError):
                        pass
            
            result = {
                'processed': created + updated,
                'created': created,
                'updated': updated,
                'output': output,
                'scraper_type': 'news_rss'
            }
            
            # Run LLM analysis for unanalyzed articles
            self._analyze_unanalyzed_articles()
            
            return result
            
        except Exception as e:
            return {'error': str(e), 'scraper_type': 'news_rss'}
        
        finally:
            sys.stdout = old_stdout

    def _execute_stock_prices(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict[str, Any]:
        """Execute stock price scraping"""
        from django.core.management import call_command
        import io
        import sys
        
        old_stdout = sys.stdout
        
        try:
            # Get configuration
            config = schedule.scraper_config or {}
            scrape_mode = config.get('scrape_mode', 'all_monitored')
            symbols = config.get('symbols', [])
            
            # Capture command output
            sys.stdout = buffer = io.StringIO()
            
            processed_count = 0
            
            if scrape_mode == 'selected_symbols' and symbols:
                # Process specific symbols (DEPRECATED - use all_monitored instead)
                for symbol in symbols:
                    call_command('collect_stock_data', '--symbol', symbol)
                    processed_count += 1
            else:
                # Process all monitored stocks using is_monitored flag (recommended approach)
                call_command('collect_stock_data', '--all')
                # Get count of monitored stocks from database
                from apps.core.models import StockSymbol
                processed_count = StockSymbol.objects.filter(is_monitored=True, is_active=True).count()
            
            output = buffer.getvalue()
            
            return {
                'processed': processed_count,
                'created': 0,
                'updated': processed_count,
                'scraper_type': 'stock_prices',
                'config': config,
                'output': output[:500]  # First 500 chars for debugging
            }
            
        except Exception as e:
            return {'error': str(e), 'scraper_type': 'stock_prices'}
        
        finally:
            sys.stdout = old_stdout

    def _execute_calendar_events(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict[str, Any]:
        """Execute calendar events scraping"""
        from django.core.management import call_command
        
        try:
            call_command('scrape_calendar')
            
            return {
                'processed': 1,  # Simplified
                'created': 0,
                'updated': 1,
                'scraper_type': 'calendar_events'
            }
            
        except Exception as e:
            return {'error': str(e), 'scraper_type': 'calendar_events'}

    def _execute_espi_reports(self, schedule: ScrapingSchedule, execution: ScrapingExecution) -> Dict[str, Any]:
        """Execute ESPI reports scraping"""
        from django.core.management import call_command
        
        try:
            call_command('scrape_espi')
            
            return {
                'processed': 1,  # Simplified
                'created': 0,
                'updated': 1,
                'scraper_type': 'espi_reports'
            }
            
        except Exception as e:
            return {'error': str(e), 'scraper_type': 'espi_reports'}

    def _analyze_unanalyzed_articles(self) -> None:
        """Run LLM analysis on articles that haven't been analyzed yet"""
        from apps.news.models import NewsArticleModel
        
        try:
            # Get recent unanalyzed articles (last 24 hours)
            unanalyzed = NewsArticleModel.objects.filter(
                is_analyzed=False,
                created_at__gte=timezone.now() - timedelta(hours=24)
            )[:10]  # Limit to 10 to avoid overwhelming the LLM
            
            logger.info(f"Found {unanalyzed.count()} unanalyzed articles for LLM analysis")
            
            for article in unanalyzed:
                try:
                    classification = self.llm_service.analyze_news_article(article)
                    if classification:
                        logger.info(f"Analyzed: {article.title[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to analyze article {article.pk}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")

    def get_schedule_status(self) -> Dict[str, Any]:
        """Get overview of all schedules and their status"""
        schedules = ScrapingSchedule.objects.all()
        
        status = {
            'total_schedules': schedules.count(),
            'active_schedules': schedules.filter(is_active=True).count(),
            'due_now': len(self.get_due_schedules()),
            'celery_available': self.celery_available,
            'execution_mode': 'async' if (self.use_celery and self.celery_available) else 'sync',
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
def run_scheduled_scrapers() -> List[ScrapingExecution]:
    """Convenience function to run all due scrapers"""
    scheduler = ScrapingScheduler()
    return scheduler.run_due_schedules()
