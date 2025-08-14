"""
Celery tasks for parallel scraper execution
"""

import logging
from typing import Dict, List, Optional
from django.utils import timezone
from django.core.management import call_command
from celery import shared_task
from io import StringIO
import sys
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, time_limit=600)  # 10 minute timeout
def execute_scraper_task(self, schedule_id: int) -> Dict:
    """
    Execute a specific scraper schedule as a Celery task
    """
    from apps.core.models import ScrapingSchedule, ScrapingExecution
    from apps.core.llm_service import LLMService
    
    execution = None
    schedule = None
    
    try:
        schedule = ScrapingSchedule.objects.get(id=schedule_id)
        
        # Create execution log
        execution = ScrapingExecution.objects.create(
            schedule=schedule,
            started_at=timezone.now()
        )
        
        # Store execution ID for tracking
        self.update_state(
            state='PROGRESS', 
            meta={
                'schedule_name': schedule.name,
                'execution_id': execution.pk,
                'started_at': execution.started_at.isoformat()
            }
        )
        
        logger.info(f"[Celery] Starting execution of {schedule.name} ({schedule.scraper_type})")
        
        # Execute based on scraper type
        if schedule.scraper_type == 'news_rss':
            result = execute_news_rss_task(schedule, execution)
        elif schedule.scraper_type == 'stock_prices':
            result = execute_stock_prices_task(schedule, execution)
        elif schedule.scraper_type == 'calendar_events':
            result = execute_calendar_events_task(schedule, execution)
        elif schedule.scraper_type == 'espi_reports':
            result = execute_espi_reports_task(schedule, execution)
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
        
        logger.info(f"[Celery] Successfully completed {schedule.name}: {result}")
        
        duration = 0
        try:
            if execution.completed_at and execution.started_at:
                # Type: ignore because we check for None above
                duration = (execution.completed_at - execution.started_at).total_seconds()  # type: ignore
        except (TypeError, AttributeError):
            duration = 0
        
        return {
            'success': True,
            'schedule_name': schedule.name,
            'execution_id': execution.pk,
            'duration': duration,
            'processed': result.get('processed', 0),
            'created': result.get('created', 0),
            'updated': result.get('updated', 0)
        }
        
    except ScrapingSchedule.DoesNotExist:
        error_msg = f"Schedule with ID {schedule_id} does not exist"
        logger.error(f"[Celery] {error_msg}")
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        logger.error(f"[Celery] Error executing schedule {schedule_id}: {str(e)}")
        
        # Update execution with error if it was created
        if execution:
            try:
                execution.success = False
                execution.error_message = str(e)
                execution.completed_at = timezone.now()
                execution.save()
            except:
                pass  # If we can't update execution, at least log the error
                
        # Mark schedule as failed if it was found
        if schedule:
            try:
                schedule.mark_execution(success=False)
            except:
                pass
            
        return {
            'success': False,
            'error': str(e),
            'schedule_id': schedule_id
        }


def execute_news_rss_task(schedule, execution) -> Dict:
    """Execute RSS news scraping"""
    # Capture command output
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        # Run the scraping command
        call_command('scrape_news')
        
        # Get output
        output = captured_output.getvalue()
        
        # Parse output for statistics
        processed = 0
        created = 0
        
        # Simple parsing - could be enhanced
        if "articles processed" in output:
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
            auto_analyze_new_articles()
        
        return {
            'processed': processed,
            'created': created,
            'updated': 0,
            'output': output,
            'auto_analyzed': config.get('auto_analyze', False)
        }
        
    except Exception as e:
        logger.error(f"[Celery] Error in news RSS scraping: {str(e)}")
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


def execute_stock_prices_task(schedule, execution) -> Dict:
    """Execute stock prices scraping"""
    # Capture command output
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        # Get scraper configuration
        config = schedule.scraper_config or {}
        scrape_mode = config.get('scrape_mode', 'all_monitored')
        symbols = config.get('symbols', [])
        
        logger.info(f"[Celery] Stock prices task - scrape_mode: {scrape_mode}, symbols: {symbols}")
        print(f"DEBUG [Celery tasks.py]: scrape_mode = {scrape_mode}")
        print(f"DEBUG [Celery tasks.py]: symbols = {symbols}")
        
        # Initialize counters
        processed = 0
        successful = 0
        failed = 0
        created = 0
        
        # Run command based on configuration
        command_success = True  # Initialize success flag
        
        if scrape_mode == 'selected_symbols' and symbols:
            # Process only selected symbols (DEPRECATED - use all_monitored instead)
            for symbol in symbols:
                try:
                    print(f"DEBUG [Celery tasks.py]: Processing symbol: {symbol}")
                    call_command('collect_stock_data', '--symbol', symbol)
                    successful += 1
                    processed += 1
                except Exception as e:
                    logger.error(f"[Celery] Error processing symbol {symbol}: {e}")
                    print(f"DEBUG [Celery tasks.py]: Error processing {symbol}: {e}")
                    failed += 1
                    processed += 1
            
            # For selected symbols, assume creation equals successful processing
            created = successful
        else:
            # Process all monitored stocks using is_monitored flag (recommended approach)
            print("DEBUG [Celery tasks.py]: Processing all monitored stocks using is_monitored flag")
            try:
                call_command('collect_stock_data', '--all')
                command_success = True
            except SystemExit as e:
                # Management command exited with non-zero code (complete failure)
                command_success = False
                if e.code != 0:
                    logger.warning(f"[Celery] collect_stock_data command failed with exit code {e.code}")
            except Exception as e:
                # Other command execution error
                command_success = False
                logger.error(f"[Celery] collect_stock_data command error: {e}")
                raise  # Re-raise to be handled by outer try/catch
            
            # Parse output for statistics when processing all stocks
            output = captured_output.getvalue()
            lines = output.split('\n')
            for line in lines:
                if "Data collection completed:" in line:
                    # Extract numbers from "Data collection completed: X/Y successful"
                    try:
                        # Handle both "INFO Data collection completed: 0/11 successful" and direct format
                        if ':' in line:
                            parts = line.split(':', 1)[1].strip()  # Get part after first colon
                        else:
                            parts = line.strip()
                        
                        if '/' in parts:
                            successful = int(parts.split('/')[0].strip())
                            processed = int(parts.split('/')[1].split()[0].strip())
                    except Exception as parse_error:
                        logger.debug(f"Failed to parse data collection line '{line}': {parse_error}")
                elif "Successful:" in line and "stocks" in line:
                    # Extract from "• Successful: 36 stocks"
                    try:
                        parts = line.split(':', 1)[1].strip()
                        if parts and parts[0].isdigit():
                            successful = int(parts.split()[0])
                    except Exception as parse_error:
                        logger.debug(f"Failed to parse successful line '{line}': {parse_error}")
                elif "Failed:" in line and "stocks" in line:
                    # Extract from "• Failed: 0 stocks"
                    try:
                        parts = line.split(':', 1)[1].strip()
                        if parts and parts[0].isdigit():
                            failed = int(parts.split()[0])
                    except Exception as parse_error:
                        logger.debug(f"Failed to parse failed line '{line}': {parse_error}")
                elif "Created new data for" in line:
                    created += 1
            
            # If we couldn't parse, set reasonable defaults
            if processed == 0 and successful > 0:
                processed = successful
            if created == 0 and successful > 0:
                created = successful
            
            # If command failed (all stocks failed), treat as error
            if not command_success:
                failed = processed if processed > 0 else 11  # Default to monitored stock count
                successful = 0
                created = 0
        
        # Get final output
        output = captured_output.getvalue()
        
        # Check if we should report this as an error
        task_success = command_success if 'command_success' in locals() else successful > 0
        
        result = {
            'processed': processed,
            'created': created,
            'updated': successful,
            'successful': successful,
            'failed': failed,
            'command_output': output[:500]  # Limit output size
        }
        
        # If complete failure, add error field to trigger exception in main task
        if not task_success and processed > 0:
            result['error'] = f"Stock data collection failed for all {processed} stocks (likely API rate limit)"
        
        return result
        
    except Exception as e:
        logger.error(f"[Celery] Error in stock prices scraping: {str(e)}")
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


def execute_calendar_events_task(schedule, execution) -> Dict:
    """Execute calendar events scraping"""
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
        logger.error(f"[Celery] Error in calendar events scraping: {str(e)}")
        return {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'command_output': captured_output.getvalue()[:500],
            'error': str(e)
        }
        
    finally:
        sys.stdout = old_stdout


def execute_espi_reports_task(schedule, execution) -> Dict:
    """Execute ESPI reports scraping"""
    # Capture command output
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    
    try:
        config = schedule.scraper_config
        report_types = config.get('report_types', ['current', 'periodic'])
        
        logger.info(f"[Celery] ESPI reports scraping - report types: {report_types}")
        print(f"DEBUG [Celery tasks.py]: ESPI scraping - report_types = {report_types}")
        
        # TODO: Implement actual ESPI scraping when command becomes available
        # For now, this is a placeholder that logs the attempt without failing
        print("INFO: ESPI scraping functionality is not yet implemented")
        print(f"Would scrape report types: {', '.join(report_types)}")
        
        # Mock successful execution for now
        processed = 0
        created = 0
        
        output = captured_output.getvalue()
        
        return {
            'processed': processed,
            'created': created,
            'updated': 0,
            'output': output,
            'report_types': report_types,
            'note': 'ESPI scraping is not yet implemented - placeholder execution'
        }
        
    except Exception as e:
        logger.error(f"[Celery] Error in ESPI reports task: {str(e)}")
        config = schedule.scraper_config or {}
        return {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'output': captured_output.getvalue(),
            'error': str(e),
            'report_types': config.get('report_types', [])
        }
        
    finally:
        sys.stdout = old_stdout


def auto_analyze_new_articles():
    """Automatically analyze new articles with AI"""
    from apps.news.models import NewsArticleModel
    from apps.core.llm_service import LLMService
    
    llm_service = LLMService()
    
    # Get unanalyzed articles
    unanalyzed = NewsArticleModel.objects.filter(
        ai_classification__isnull=True
    )[:5]  # Limit to 5 for performance
    
    if unanalyzed:
        logger.info(f"[Celery] Auto-analyzing {len(unanalyzed)} new articles")
        
        for article in unanalyzed:
            try:
                classification = llm_service.analyze_news_article(article)
                if classification:
                    logger.info(f"[Celery] Analyzed: {article.title[:50]}...")
            except Exception as e:
                logger.warning(f"[Celery] Failed to analyze article {article.pk}: {e}")


@shared_task
def run_due_schedules_parallel() -> Dict:
    """
    Check for due schedules and run them in parallel using Celery tasks
    This is a simplified implementation that doesn't launch parallel tasks
    to avoid circular import issues
    """
    from apps.core.models import ScrapingSchedule
    from apps.core.scheduler_service import ScrapingScheduler
    
    logger.info("[Celery] Checking for due schedules")
    
    # Get all schedules that are due to run
    due_schedules = []
    
    for schedule in ScrapingSchedule.objects.filter(is_active=True):
        if schedule.should_run_now():
            due_schedules.append(schedule)
    
    if not due_schedules:
        logger.info("[Celery] No schedules due for execution")
        return {
            'success': True,
            'due_schedules': 0,
            'executed': 0
        }
    
    logger.info(f"[Celery] Found {len(due_schedules)} schedules due for execution")
    
    # Execute schedules sequentially to avoid conflicts
    executed_count = 0
    scheduler = ScrapingScheduler(use_celery=False)
    
    for schedule in due_schedules:
        try:
            execution = scheduler.execute_schedule(schedule)
            if execution.success:
                executed_count += 1
                logger.info(f"[Celery] Successfully executed {schedule.name}")
            else:
                logger.error(f"[Celery] Failed to execute {schedule.name}: {execution.error_message}")
            
        except Exception as e:
            logger.error(f"[Celery] Failed to execute schedule {schedule.name}: {e}")
    
    return {
        'success': True,
        'due_schedules': len(due_schedules),
        'executed': executed_count
    }


@shared_task
def run_specific_scraper(schedule_id: int) -> Dict:
    """
    Run a specific scraper manually (for AJAX calls)
    """
    # Call the task directly instead of importing it
    return execute_scraper_task(None, schedule_id)


@shared_task(bind=True, ignore_result=True)
def run_scheduled_scrapers_beat_task(self):
    """
    Celery Beat task to run scheduled scrapers automatically
    This should be called periodically (every minute) by Celery Beat
    """
    try:
        logger.info("[Beat] Running scheduled scrapers task")
        
        from apps.core.scheduler_service import ScrapingScheduler
        scheduler = ScrapingScheduler()
        executions = scheduler.run_due_schedules()
        
        if executions:
            success_count = sum(1 for ex in executions if ex.success)
            error_count = len(executions) - success_count
            
            logger.info(
                f"[Beat] Scheduled scrapers completed: {success_count} succeeded, {error_count} failed"
            )
        else:
            logger.debug("[Beat] No scrapers were due for execution")
            
        return {
            'success': True,
            'executions_count': len(executions) if executions else 0,
            'success_count': sum(1 for ex in executions if ex.success) if executions else 0
        }
        
    except Exception as e:
        logger.error(f"[Beat] Error running scheduled scrapers: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(time_limit=300)  # 5 minute timeout
def detect_anomalies_task() -> Dict:
    """
    Periodic task to automatically detect anomalies in stock data
    """
    from apps.analysis.ml_models import MLModelManager
    from apps.core.models import StockSymbol, TradingSession
    from apps.scrapers.models import StockData
    from apps.analysis.models import AnomalyAlert
    from datetime import date, timedelta
    import torch
    
    try:
        logger.info("[Anomaly] Starting automatic anomaly detection")
        
        # Initialize ML manager
        ml_manager = MLModelManager()
        
        # Check if anomaly detector is trained
        if not hasattr(ml_manager, 'anomaly_detector') or ml_manager.anomaly_detector is None:
            logger.warning("[Anomaly] Anomaly detector not trained, skipping detection")
            return {
                'success': False,
                'message': 'Anomaly detector not trained',
                'anomalies_detected': 0
            }
        
        # Get current trading session
        latest_session = TradingSession.objects.order_by('-date').first()
        if not latest_session:
            logger.warning("[Anomaly] No trading session available")
            return {
                'success': False,
                'message': 'No trading session available',
                'anomalies_detected': 0
            }
        
        # Get monitored stocks
        monitored_stocks = StockSymbol.objects.filter(is_monitored=True)
        detected_anomalies = []
        anomaly_count = 0
        
        # Update task state
        logger.info(f"[Anomaly] Analyzing {monitored_stocks.count()} monitored stocks for session {latest_session.date}")
        
        for i, stock in enumerate(monitored_stocks):
            try:
                # Update progress
                logger.debug(f"[Anomaly] Analyzing stock {i+1}/{monitored_stocks.count()}: {stock.symbol}")
                
                # Get recent stock data for anomaly detection
                recent_data = StockData.objects.filter(
                    stock=stock,
                    trading_session__date__gte=latest_session.date - timedelta(days=3)
                ).order_by('-trading_session__date', '-data_timestamp')[:15]
                
                if recent_data.count() < 10:
                    logger.debug(f"[Anomaly] Insufficient data for {stock.symbol}")
                    continue
                
                # Analyze recent data points for anomalies
                data_points = list(recent_data)
                
                # Check only the most recent data points (last 3)
                for j, current_data in enumerate(data_points[:3]):
                    
                    # Skip if this anomaly was already detected today
                    existing_alert = AnomalyAlert.objects.filter(
                        stock=stock,
                        trading_session=current_data.trading_session,
                        created_at__date=date.today(),
                        is_active=True
                    ).exists()
                    
                    if existing_alert:
                        continue
                    
                    # Extract features for anomaly detection
                    features = ml_manager._extract_anomaly_features(data_points[j:], 0, stock)
                    if features is None or len(features) != 25:
                        continue
                    
                    # Convert to tensor and detect anomaly
                    features_tensor = torch.FloatTensor([features])
                    ml_manager.anomaly_detector.eval()
                    
                    with torch.no_grad():
                        reconstructed, anomaly_score = ml_manager.anomaly_detector(features_tensor)
                    
                    anomaly_score = anomaly_score.item()
                    threshold = getattr(ml_manager, 'anomaly_threshold', 0.5)
                    
                    # If anomaly detected, create alert
                    if anomaly_score > threshold:
                        anomaly_count += 1
                        
                        # Classify anomaly type
                        anomaly_type = ml_manager._classify_anomaly_type(features, current_data)
                        
                        # Create anomaly alert in database
                        anomaly_alert = AnomalyAlert.objects.create(
                            stock=stock,
                            trading_session=current_data.trading_session,
                            anomaly_type=anomaly_type,
                            confidence_score=float(anomaly_score),
                            severity=4 if anomaly_score > 0.8 else 3,  # High/Medium severity
                            description=f"Automatic anomaly detection: {anomaly_type} in {stock.symbol}",
                            detection_details={
                                'anomaly_score': float(anomaly_score),
                                'threshold': float(threshold),
                                'features_analyzed': len(features),
                                'detection_method': 'automatic_periodic',
                                'model_version': 'v1.0',
                                'detection_time': timezone.now().isoformat()
                            },
                            is_active=True
                        )
                        
                        detected_anomalies.append({
                            'id': anomaly_alert.pk,
                            'stock_symbol': stock.symbol,
                            'anomaly_type': anomaly_type,
                            'confidence': float(anomaly_score),
                            'severity': anomaly_alert.severity,
                            'session_date': current_data.trading_session.date.isoformat()
                        })
                        
                        logger.info(f"[Anomaly] Detected {anomaly_type} in {stock.symbol}: {anomaly_score:.3f}")
                        
                        # Limit to prevent overwhelming the system
                        if anomaly_count >= 20:
                            logger.info("[Anomaly] Reached anomaly limit (20), stopping detection")
                            break
                
                # Break outer loop if limit reached
                if anomaly_count >= 20:
                    break
            
            except Exception as e:
                logger.error(f"[Anomaly] Error analyzing {stock.symbol}: {e}")
                continue
        
        # Final result
        result = {
            'success': True,
            'message': f'Anomaly detection completed',
            'anomalies_detected': anomaly_count,
            'stocks_analyzed': monitored_stocks.count(),
            'session_date': latest_session.date.isoformat(),
            'detection_time': timezone.now().isoformat()
        }
        
        if anomaly_count > 0:
            result['anomalies'] = detected_anomalies[:10]  # Include top 10
        
        logger.info(f"[Anomaly] Detection completed: {anomaly_count} anomalies found in {monitored_stocks.count()} stocks")
        return result
        
    except Exception as e:
        logger.error(f"[Anomaly] Error in automatic anomaly detection: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'anomalies_detected': 0
        }


@shared_task(bind=True, time_limit=300)  # 5 minute timeout
def update_daily_trading_signals_task(self) -> Dict:
    """
    Update outcomes for daily trading signals and calculate intraday performance.
    Runs every 30 minutes during trading hours to track signal performance.
    """
    try:
        from apps.analysis.daily_trading_performance import DailyTradingPerformanceAnalyzer
        from django.utils import timezone
        import pytz
        
        # Check if we're in trading hours (9 AM - 5 PM Warsaw time)
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        current_time_warsaw = timezone.now().astimezone(warsaw_tz)
        current_hour = current_time_warsaw.hour
        
        logger.info(f"[Daily Trading] Starting signal update task at {current_time_warsaw.strftime('%H:%M:%S')}")
        
        # Initialize analyzer
        analyzer = DailyTradingPerformanceAnalyzer()
        
        # Update signal outcomes
        update_results = analyzer.update_intraday_signal_outcomes()
        
        # Calculate today's performance metrics
        daily_metrics = analyzer.calculate_daily_performance()
        
        # Get hourly breakdown
        hourly_breakdown = analyzer.get_hourly_performance_breakdown()
        
        # Store results for ML feedback (will implement this next)
        performance_data = {
            'trading_date': timezone.now().date().isoformat(),
            'update_time': timezone.now().isoformat(),
            'signals_updated': update_results['updated'],
            'total_signals_today': daily_metrics.total_signals,
            'win_rate': daily_metrics.win_rate,
            'total_return': daily_metrics.total_return_today,
            'avg_return_per_hour': daily_metrics.avg_return_per_hour,
            'pending_signals': daily_metrics.pending_signals,
            'hourly_performance': [
                {
                    'hour': h.hour,
                    'signals': h.signals_generated,
                    'win_rate': h.win_rate,
                    'avg_return': h.avg_return
                } for h in hourly_breakdown
            ]
        }
        
        # If it's after market close (5 PM), finalize all pending signals
        if current_hour >= 17:
            logger.info("[Daily Trading] Market closed - finalizing all pending signals")
            final_update = analyzer.update_intraday_signal_outcomes()
            update_results['final_updated'] = final_update['updated']
            update_results['final_processed'] = final_update['processed']
        
        result = {
            'success': True,
            'message': 'Daily trading signals updated successfully',
            'signals_updated': update_results['updated'],
            'signals_processed': update_results['processed'],
            'errors': update_results['errors'],
            'performance_data': performance_data,
            'is_trading_hours': 9 <= current_hour <= 17,
            'current_time': current_time_warsaw.strftime('%H:%M:%S')
        }
        
        logger.info(f"[Daily Trading] Task completed: {update_results['updated']} signals updated, "
                   f"{daily_metrics.total_signals} total signals today, "
                   f"{daily_metrics.win_rate:.2f}% win rate")
        
        return result
        
    except Exception as e:
        logger.error(f"[Daily Trading] Error in signal update task: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'signals_updated': 0
        }


@shared_task(bind=True, time_limit=600)  # 10 minute timeout
def ml_recommendation_feedback_task(self) -> Dict:
    """
    Analyze recommendation performance and generate ML feedback.
    Runs daily after market close to analyze the day's performance and generate insights.
    """
    try:
        from apps.analysis.ml_recommendation_feedback import MLRecommendationFeedbackSystem
        from django.utils import timezone
        import pytz
        
        logger.info("[ML Feedback] Starting recommendation feedback analysis")
        
        # Initialize feedback system
        feedback_system = MLRecommendationFeedbackSystem()
        
        # Analyze last 7 days of recommendation quality
        feedbacks = feedback_system.analyze_recommendation_quality(days_back=7)
        
        # Identify performance patterns over last 30 days
        patterns = feedback_system.identify_performance_patterns(days_back=30)
        
        # Generate improvement recommendations
        improvements = feedback_system.generate_improvement_recommendations(feedbacks, patterns)
        
        # Store feedback data for ML learning
        storage_results = feedback_system.store_feedback_for_ml(feedbacks, patterns)
        
        # Prepare summary statistics
        total_feedbacks = len(feedbacks)
        critical_issues = len(improvements['critical_issues'])
        optimization_opportunities = len(improvements['optimization_opportunities'])
        high_performers = len([f for f in feedbacks if f.actual_accuracy > 80])
        low_performers = len([f for f in feedbacks if f.actual_accuracy < 50])
        
        # Calculate average improvement score
        avg_improvement_score = sum(f.improvement_score for f in feedbacks) / total_feedbacks if feedbacks else 0
        
        result = {
            'success': True,
            'message': 'ML recommendation feedback analysis completed',
            'analysis_summary': {
                'total_feedbacks': total_feedbacks,
                'critical_issues': critical_issues,
                'optimization_opportunities': optimization_opportunities,
                'high_performers': high_performers,
                'low_performers': low_performers,
                'avg_improvement_score': round(avg_improvement_score, 2)
            },
            'patterns_identified': len(patterns),
            'storage_results': storage_results,
            'improvements_generated': {
                'critical_issues': critical_issues,
                'optimizations': optimization_opportunities,
                'model_adjustments': len(improvements['model_adjustments']),
                'strategy_changes': len(improvements['strategy_changes'])
            },
            'analysis_time': timezone.now().isoformat()
        }
        
        # Log key insights
        if critical_issues > 0:
            logger.warning(f"[ML Feedback] {critical_issues} critical performance issues identified")
        
        if high_performers > 0:
            logger.info(f"[ML Feedback] {high_performers} high-performing recommendation types found")
            
        logger.info(f"[ML Feedback] Analysis completed: {total_feedbacks} feedbacks analyzed, "
                   f"{len(patterns)} patterns identified, {storage_results['stored']} records stored")
        
        return result
        
    except Exception as e:
        logger.error(f"[ML Feedback] Error in recommendation feedback analysis: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'feedbacks_analyzed': 0
        }


@shared_task(bind=True)
def price_based_trigger_analysis_task(self) -> Dict:
    """
    Real-time price monitoring task that triggers immediate analysis
    when significant market movements are detected.
    """
    try:
        from apps.analysis.price_trigger_service import run_price_trigger_analysis
        
        logger.info("[PriceTrigger] Starting price-based trigger analysis")
        
        # Run the price trigger analysis
        result = run_price_trigger_analysis()
        
        if result['success']:
            # Log summary
            logger.info(
                f"[PriceTrigger] Analysis completed: "
                f"{result['monitored_stocks']} stocks monitored, "
                f"{result['trigger_events']} trigger events found, "
                f"{result['signals_generated']} priority signals generated"
            )
            
            # Send alerts for high-priority events if any signals were generated
            if result['signals_generated'] > 0:
                try:
                    from apps.notifications.alert_service import TradingAlertService
                    from apps.analysis.models import TradingSignal
                    
                    alert_service = TradingAlertService()
                    
                    # Get priority signals generated in last 5 minutes
                    recent_signals = TradingSignal.objects.filter(
                        created_at__gte=timezone.now() - timedelta(minutes=5),
                        notes__icontains='Priority signal triggered by'
                    ).select_related('stock')
                    
                    alerts_sent = 0
                    for signal in recent_signals:
                        alert_result = alert_service.send_signal_alert(signal)
                        if alert_result.get('success'):
                            alerts_sent += 1
                    
                    if alerts_sent > 0:
                        logger.info(f"[PriceTrigger] {alerts_sent} priority signal alerts sent successfully")
                    else:
                        logger.warning(f"[PriceTrigger] No alerts sent for {recent_signals.count()} priority signals")
                        
                except Exception as alert_error:
                    logger.warning(f"[PriceTrigger] Alert notification error: {alert_error}")
            
            return {
                'success': True,
                'task_result': result,
                'alerts_sent': result['signals_generated'] > 0
            }
        else:
            logger.error(f"[PriceTrigger] Analysis failed: {result.get('error', 'Unknown error')}")
            return result
            
    except Exception as e:
        logger.error(f"[PriceTrigger] Task execution error: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'task_timestamp': timezone.now().isoformat()
        }
