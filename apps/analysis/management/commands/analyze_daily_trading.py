"""
Management command for daily trading recommendation analysis and feedback.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta, date
from typing import Optional

from apps.analysis.daily_trading_performance import DailyTradingPerformanceAnalyzer
from apps.analysis.ml_recommendation_feedback import MLRecommendationFeedbackSystem


class Command(BaseCommand):
    help = 'Analyze daily trading recommendation performance and generate ML feedback'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-signals',
            action='store_true',
            help='Update outcomes for pending signals'
        )
        
        parser.add_argument(
            '--analyze-performance',
            action='store_true', 
            help='Analyze daily trading performance'
        )
        
        parser.add_argument(
            '--generate-feedback',
            action='store_true',
            help='Generate ML feedback and improvement recommendations'
        )
        
        parser.add_argument(
            '--trading-date',
            type=str,
            help='Specific trading date to analyze (YYYY-MM-DD, default: today)'
        )
        
        parser.add_argument(
            '--feedback-days',
            type=int,
            default=7,
            help='Number of days to analyze for feedback (default: 7)'
        )
        
        parser.add_argument(
            '--pattern-days',
            type=int,
            default=30,
            help='Number of days to analyze for patterns (default: 30)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting daily trading recommendation analysis...')
        )

        # Parse trading date
        trading_date = None
        if options['trading_date']:
            try:
                trading_date = datetime.strptime(options['trading_date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')
        else:
            trading_date = timezone.now().date()

        # Initialize analyzers
        daily_analyzer = DailyTradingPerformanceAnalyzer()
        feedback_system = MLRecommendationFeedbackSystem()

        # Update signals if requested
        if options['update_signals']:
            self._update_signals(daily_analyzer)

        # Analyze performance if requested
        if options['analyze_performance']:
            self._analyze_performance(daily_analyzer, trading_date)

        # Generate feedback if requested
        if options['generate_feedback']:
            self._generate_feedback(
                feedback_system, 
                options['feedback_days'], 
                options['pattern_days']
            )

        # If no specific action requested, do all
        if not any([
            options['update_signals'], 
            options['analyze_performance'], 
            options['generate_feedback']
        ]):
            self._update_signals(daily_analyzer)
            self._analyze_performance(daily_analyzer, trading_date)
            self._generate_feedback(feedback_system, options['feedback_days'], options['pattern_days'])

        self.stdout.write(
            self.style.SUCCESS('Daily trading recommendation analysis completed!')
        )

    def _update_signals(self, analyzer: DailyTradingPerformanceAnalyzer):
        """Update signal outcomes"""
        self.stdout.write("Updating signal outcomes...")
        
        try:
            results = analyzer.update_intraday_signal_outcomes()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Signal update completed:\n"
                    f"  - Processed: {results['processed']} signals\n"
                    f"  - Updated: {results['updated']} signals\n"
                    f"  - Errors: {results['errors']} signals"
                )
            )
            
            if results['errors'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"Warning: {results['errors']} signals had errors during update")
                )
                
        except Exception as e:
            raise CommandError(f"Error updating signals: {str(e)}")

    def _analyze_performance(self, analyzer: DailyTradingPerformanceAnalyzer, trading_date: date):
        """Analyze daily trading performance"""
        self.stdout.write(f"Analyzing performance for {trading_date}...")
        
        try:
            # Calculate daily metrics
            daily_metrics = analyzer.calculate_daily_performance(trading_date)
            
            # Get hourly breakdown
            hourly_breakdown = analyzer.get_hourly_performance_breakdown(trading_date)
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS(
                    f"Performance Analysis for {trading_date}:\n"
                    f"  - Total Signals: {daily_metrics.total_signals}\n"
                    f"  - Profitable: {daily_metrics.profitable_signals}\n"
                    f"  - Loss: {daily_metrics.loss_signals}\n"
                    f"  - Pending: {daily_metrics.pending_signals}\n"
                    f"  - Win Rate: {daily_metrics.win_rate:.2f}%\n"
                    f"  - Average Return per Hour: {daily_metrics.avg_return_per_hour:.2f}%\n"
                    f"  - Total Return Today: {daily_metrics.total_return_today:.2f}%\n"
                    f"  - Best Signal Return: {daily_metrics.best_signal_return:.2f}%\n"
                    f"  - Worst Signal Return: {daily_metrics.worst_signal_return:.2f}%\n"
                    f"  - Average Signal Duration: {daily_metrics.avg_signal_duration_hours:.2f} hours\n"
                    f"  - Signals Hit Target: {daily_metrics.signals_hit_target}\n"
                    f"  - Signals Hit Stop: {daily_metrics.signals_hit_stop}"
                )
            )
            
            # Display hourly breakdown if available
            if hourly_breakdown:
                self.stdout.write("\nHourly Performance Breakdown:")
                for hour_data in hourly_breakdown:
                    self.stdout.write(
                        f"  {hour_data.hour:02d}:00 - Signals: {hour_data.signals_generated}, "
                        f"Win Rate: {hour_data.win_rate:.1f}%, Avg Return: {hour_data.avg_return:.2f}%"
                    )
                
        except Exception as e:
            raise CommandError(f"Error analyzing performance: {str(e)}")

    def _generate_feedback(self, feedback_system: MLRecommendationFeedbackSystem, feedback_days: int, pattern_days: int):
        """Generate ML feedback"""
        self.stdout.write(f"Generating ML feedback (analyzing last {feedback_days} days for quality, {pattern_days} days for patterns)...")
        
        try:
            # Analyze recommendation quality
            feedbacks = feedback_system.analyze_recommendation_quality(days_back=feedback_days)
            
            # Identify performance patterns
            patterns = feedback_system.identify_performance_patterns(days_back=pattern_days)
            
            # Generate improvement recommendations
            improvements = feedback_system.generate_improvement_recommendations(feedbacks, patterns)
            
            # Store feedback for ML
            storage_results = feedback_system.store_feedback_for_ml(feedbacks, patterns)
            
            # Display summary
            self.stdout.write(
                self.style.SUCCESS(
                    f"ML Feedback Analysis Completed:\n"
                    f"  - Total Feedbacks: {len(feedbacks)}\n"
                    f"  - Patterns Identified: {len(patterns)}\n"
                    f"  - Storage Results: {storage_results['stored']} stored, {storage_results['errors']} errors"
                )
            )
            
            # Display critical issues
            if improvements['critical_issues']:
                self.stdout.write(
                    self.style.ERROR(
                        f"\nCritical Issues ({len(improvements['critical_issues'])}):"
                    )
                )
                for issue in improvements['critical_issues']:
                    self.stdout.write(f"  - {issue['issue']} (accuracy: {issue['accuracy']:.1f}%)")
                    self.stdout.write(f"    Recommendation: {issue['recommendation']}")
            
            # Display optimization opportunities
            if improvements['optimization_opportunities']:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nOptimization Opportunities ({len(improvements['optimization_opportunities'])}):"
                    )
                )
                for opp in improvements['optimization_opportunities']:
                    self.stdout.write(f"  - {opp['opportunity']} (accuracy: {opp['accuracy']:.1f}%)")
                    self.stdout.write(f"    Suggestion: {opp['suggestion']}")
            
            # Display model adjustments
            if improvements['model_adjustments']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nModel Adjustments ({len(improvements['model_adjustments'])}):"
                    )
                )
                for adj in improvements['model_adjustments']:
                    self.stdout.write(f"  - {adj['pattern']} (impact: {adj['impact']:.2f})")
                    self.stdout.write(f"    Action: {adj['action']}")
            
            # Display strategy changes
            if improvements['strategy_changes']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nStrategy Changes ({len(improvements['strategy_changes'])}):"
                    )
                )
                for change in improvements['strategy_changes']:
                    self.stdout.write(f"  - {change['strategy']}")
                    self.stdout.write(f"    Rationale: {change['rationale']}")
                    
            # Show top performing and worst performing feedbacks
            if feedbacks:
                best_performers = sorted(feedbacks, key=lambda x: x.actual_accuracy, reverse=True)[:3]
                worst_performers = sorted(feedbacks, key=lambda x: x.actual_accuracy)[:3]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nTop Performers:"
                    )
                )
                for perf in best_performers:
                    self.stdout.write(
                        f"  - {perf.stock_symbol} {perf.signal_type}: {perf.actual_accuracy:.1f}% accuracy, "
                        f"{perf.avg_roi:.2f}% ROI"
                    )
                
                self.stdout.write(
                    self.style.ERROR(
                        f"\nWorst Performers:"
                    )
                )
                for perf in worst_performers:
                    self.stdout.write(
                        f"  - {perf.stock_symbol} {perf.signal_type}: {perf.actual_accuracy:.1f}% accuracy, "
                        f"{perf.avg_roi:.2f}% ROI"
                    )
                    self.stdout.write(f"    Notes: {perf.feedback_notes}")
                
        except Exception as e:
            raise CommandError(f"Error generating feedback: {str(e)}")
