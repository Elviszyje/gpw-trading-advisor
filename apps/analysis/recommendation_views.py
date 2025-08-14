"""
Recommendation Performance Analysis Views
Comprehensive dashboard for tracking ML recommendation accuracy and outcomes
Updated for daily trading with intraday performance tracking
"""

import json
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q, Sum
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import TradingSignal, PredictionResult, StockSymbol, TradingSession
from .performance_tracking import SignalPerformanceAnalyzer
from .daily_trading_performance import DailyTradingPerformanceAnalyzer
from .ml_recommendation_feedback import MLRecommendationFeedbackSystem

# Conditionally import ML components if torch is available
try:
    from .ml_engine import RecommendationFeedbackTracker
    ML_ENGINE_AVAILABLE = True
except ImportError:
    ML_ENGINE_AVAILABLE = False
    RecommendationFeedbackTracker = None

import logging
logger = logging.getLogger(__name__)


@login_required
@login_required
def recommendation_dashboard(request):
    """
    Main recommendation performance dashboard - optimized for daily trading
    """
    try:
        # Initialize analyzers - both daily and traditional
        daily_analyzer = DailyTradingPerformanceAnalyzer()
        traditional_analyzer = SignalPerformanceAnalyzer()
        
        # Get today's trading date
        today = timezone.now().date()
        
        # Calculate today's performance metrics
        daily_metrics = daily_analyzer.calculate_daily_performance(today)
        
        # Get hourly performance breakdown for today
        hourly_breakdown = daily_analyzer.get_hourly_performance_breakdown(today)
        
        # Get recent signals (today and last 7 days for comparison)
        today_signals = TradingSignal.objects.filter(
            trading_session__date=today,
            generated_by='daily_trading_system'
        ).order_by('-created_at')[:20]
        
        recent_signals = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')[:10]
        
        # Calculate traditional metrics for comparison (last 30 days)
        traditional_metrics = traditional_analyzer.calculate_signal_performance()
        
        # Get overall statistics
        total_signals_all_time = TradingSignal.objects.count()
        signals_with_outcomes = TradingSignal.objects.exclude(actual_outcome='pending').count()
        
        # Get accuracy metrics (updated for daily trading)
        accuracy_data = _calculate_daily_accuracy_metrics()
        
        # Get performance trends (last 7 days)
        trend_data = _get_daily_performance_trends()
        
        # Get model learning statistics
        learning_stats = _get_learning_statistics()
        
        # Calculate key metrics for display
        context = {
            # Today's performance
            'daily_metrics': daily_metrics,
            'hourly_breakdown': hourly_breakdown,
            'today_signals': today_signals,
            
            # Historical comparison
            'recent_signals': recent_signals,
            'traditional_metrics': traditional_metrics,
            
            # Overall statistics
            'total_signals': total_signals_all_time,
            'signals_with_outcomes': signals_with_outcomes,
            'completion_rate': (signals_with_outcomes / total_signals_all_time * 100) if total_signals_all_time > 0 else 0,
            
            # Analysis data
            'accuracy_data': accuracy_data,
            'trend_data': trend_data,
            'learning_stats': learning_stats,
            
            # Display flags
            'is_daily_trading_mode': True,
            'current_time': timezone.now(),
            'trading_date': today
        }
        
        return render(request, 'analysis/recommendation_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error in recommendation dashboard: {e}", exc_info=True)
        return render(request, 'analysis/recommendation_dashboard.html', {
            'error': f"Error loading dashboard: {str(e)}",
            'is_daily_trading_mode': True,
            'current_time': timezone.now()
        })


@login_required
def recommendation_details(request):
    """
    Detailed view of all recommendations with outcomes
    """
    try:
        # Get filter parameters
        days = int(request.GET.get('days', 30))
        symbol = request.GET.get('symbol', '')
        signal_type = request.GET.get('signal_type', '')
        
        # Build query
        queryset = TradingSignal.objects.all()
        
        if days > 0:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=start_date)
            
        if symbol:
            queryset = queryset.filter(stock__symbol__icontains=symbol)
            
        if signal_type:
            queryset = queryset.filter(signal_type=signal_type)
        
        # Order by most recent first
        signals = queryset.order_by('-created_at').select_related('stock')
        
        # Add outcome analysis for each signal
        signals_with_analysis = []
        for signal in signals:
            analysis = _analyze_signal_outcome(signal)
            signals_with_analysis.append({
                'signal': signal,
                'analysis': analysis
            })
        
        # Get available symbols for filter
        symbols = StockSymbol.objects.filter(is_active=True).values_list('symbol', flat=True)
        
        context = {
            'signals_data': signals_with_analysis,
            'symbols': symbols,
            'filters': {
                'days': days,
                'symbol': symbol,
                'signal_type': signal_type
            }
        }
        
        return render(request, 'analysis/recommendation_details.html', context)
        
    except Exception as e:
        return render(request, 'analysis/recommendation_details.html', {
            'error': f"Error loading recommendations: {str(e)}"
        })


@login_required
def learning_analytics(request):
    """
    Analytics page showing model learning progress and effectiveness
    """
    try:
        if not ML_ENGINE_AVAILABLE:
            return render(request, 'analysis/learning_analytics.html', {
                'error': 'ML engine not available. Please install torch and related dependencies.'
            })
        
        # Get feedback tracker instance
        feedback_tracker = RecommendationFeedbackTracker()
        
        # Calculate model performance over time
        performance_history = _get_model_performance_history()
        
        # Get learning effectiveness metrics
        learning_metrics = _calculate_learning_effectiveness()
        
        # Get feedback contribution analysis
        feedback_analysis = _analyze_feedback_contributions()
        
        context = {
            'performance_history': performance_history,
            'learning_metrics': learning_metrics,
            'feedback_analysis': feedback_analysis
        }
        
        return render(request, 'analysis/learning_analytics.html', context)
        
    except Exception as e:
        return render(request, 'analysis/learning_analytics.html', {
            'error': f"Error loading learning analytics: {str(e)}"
        })


@login_required
@csrf_exempt
def api_recommendation_stats(request):
    """
    API endpoint for real-time recommendation statistics
    """
    try:
        days = int(request.GET.get('days', 7))
        
        # Calculate statistics for the period
        start_date = timezone.now() - timedelta(days=days)
        
        signals = TradingSignal.objects.filter(created_at__gte=start_date)
        signals_with_outcomes = signals.exclude(outcome_price__isnull=True)
        
        # Calculate accuracy based on profitable outcomes
        profitable_predictions = signals_with_outcomes.filter(
            actual_outcome='profitable'
        ).count()
        
        total_with_outcomes = signals_with_outcomes.count()
        accuracy = (profitable_predictions / total_with_outcomes * 100) if total_with_outcomes > 0 else 0
        
        # Calculate ROI
        total_roi = 0
        roi_count = 0
        for signal in signals_with_outcomes:
            roi = _calculate_signal_roi(signal)
            if roi is not None:
                total_roi += roi
                roi_count += 1
        
        avg_roi = total_roi / roi_count if roi_count > 0 else 0
        
        # Calculate win/loss ratio
        winning_signals = 0
        losing_signals = 0
        for signal in signals_with_outcomes:
            roi = _calculate_signal_roi(signal)
            if roi is not None:
                if roi > 0:
                    winning_signals += 1
                elif roi < 0:
                    losing_signals += 1
        
        win_rate = (winning_signals / total_with_outcomes * 100) if total_with_outcomes > 0 else 0
        
        # Daily breakdown
        daily_stats = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_signals = signals.filter(
                created_at__date=day.date()
            )
            day_with_outcomes = day_signals.exclude(outcome_price__isnull=True)
            day_profitable = day_with_outcomes.filter(actual_outcome='profitable').count()
            day_total = day_with_outcomes.count()
            day_accuracy = (day_profitable / day_total * 100) if day_total > 0 else 0
            
            daily_stats.append({
                'date': day.strftime('%Y-%m-%d'),
                'accuracy': round(day_accuracy, 2),
                'total_signals': day_signals.count(),
                'completed_signals': day_total
            })
        
        return JsonResponse({
            'status': 'success',
            'period_days': days,
            'overall_accuracy': round(accuracy, 2),
            'average_roi': round(float(total_roi), 2),
            'win_rate': round(win_rate, 2),
            'total_signals': signals.count(),
            'completed_signals': total_with_outcomes,
            'daily_stats': daily_stats
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _calculate_accuracy_metrics():
    """Calculate various accuracy metrics for recommendations"""
    try:
        # Get signals with outcomes from last 30 days
        recent_signals = TradingSignal.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).exclude(outcome_price__isnull=True)
        
        if not recent_signals.exists():
            return {
                'overall_accuracy': 0,
                'buy_accuracy': 0,
                'sell_accuracy': 0,
                'hold_accuracy': 0,
                'average_roi': 0
            }
        
        # Calculate accuracy based on actual outcomes
        profitable_signals = recent_signals.filter(actual_outcome='profitable').count()
        total_signals = recent_signals.count()
        overall_accuracy = (profitable_signals / total_signals * 100) if total_signals > 0 else 0
        
        # Accuracy by signal type
        buy_signals = recent_signals.filter(signal_type='buy')
        sell_signals = recent_signals.filter(signal_type='sell')
        hold_signals = recent_signals.filter(signal_type='hold')
        
        buy_accuracy = _calculate_type_accuracy(buy_signals)
        sell_accuracy = _calculate_type_accuracy(sell_signals)
        hold_accuracy = _calculate_type_accuracy(hold_signals)
        
        # Calculate Average ROI based on actual price movements
        total_roi = 0
        roi_count = 0
        for signal in recent_signals:
            roi = _calculate_signal_roi(signal)
            if roi is not None:
                total_roi += roi
                roi_count += 1
        
        avg_roi = total_roi / roi_count if roi_count > 0 else 0
        
        return {
            'overall_accuracy': round(overall_accuracy, 2),
            'buy_accuracy': round(buy_accuracy, 2),
            'sell_accuracy': round(sell_accuracy, 2),
            'hold_accuracy': round(hold_accuracy, 2),
            'average_roi': round(avg_roi, 2)
        }
        
    except Exception as e:
        print(f"Error calculating accuracy metrics: {e}")
        return {
            'overall_accuracy': 0,
            'buy_accuracy': 0,
            'sell_accuracy': 0,
            'hold_accuracy': 0,
            'average_roi': 0
        }


def _calculate_daily_accuracy_metrics():
    """Calculate accuracy metrics optimized for daily trading (today's signals)"""
    try:
        today = timezone.now().date()
        
        # Get today's signals with outcomes
        today_signals = TradingSignal.objects.filter(
            trading_session__date=today,
            generated_by='daily_trading_system'
        ).exclude(actual_outcome='pending')
        
        if not today_signals.exists():
            return {
                'today_accuracy': 0,
                'today_buy_accuracy': 0,
                'today_sell_accuracy': 0,
                'today_hold_accuracy': 0,
                'today_average_roi': 0,
                'completed_signals_today': 0,
                'pending_signals_today': 0
            }
        
        # Calculate today's accuracy
        profitable_today = today_signals.filter(actual_outcome='profitable').count()
        total_today = today_signals.count()
        today_accuracy = (profitable_today / total_today * 100) if total_today > 0 else 0
        
        # Accuracy by signal type for today
        buy_signals_today = today_signals.filter(signal_type='buy')
        sell_signals_today = today_signals.filter(signal_type='sell')
        hold_signals_today = today_signals.filter(signal_type='hold')
        
        today_buy_accuracy = _calculate_type_accuracy(buy_signals_today)
        today_sell_accuracy = _calculate_type_accuracy(sell_signals_today)
        today_hold_accuracy = _calculate_type_accuracy(hold_signals_today)
        
        # Calculate today's average ROI
        total_roi = 0
        roi_count = 0
        for signal in today_signals:
            roi = _calculate_signal_roi(signal)
            if roi is not None:
                total_roi += roi
                roi_count += 1
        
        today_avg_roi = total_roi / roi_count if roi_count > 0 else 0
        
        # Count pending signals for today
        pending_today = TradingSignal.objects.filter(
            trading_session__date=today,
            generated_by='daily_trading_system',
            actual_outcome='pending'
        ).count()
        
        return {
            'today_accuracy': round(today_accuracy, 2),
            'today_buy_accuracy': round(today_buy_accuracy, 2),
            'today_sell_accuracy': round(today_sell_accuracy, 2),
            'today_hold_accuracy': round(today_hold_accuracy, 2),
            'today_average_roi': round(today_avg_roi, 2),
            'completed_signals_today': total_today,
            'pending_signals_today': pending_today
        }
        
    except Exception as e:
        logger.error(f"Error calculating daily accuracy metrics: {e}")
        return {
            'today_accuracy': 0,
            'today_buy_accuracy': 0,
            'today_sell_accuracy': 0,
            'today_hold_accuracy': 0,
            'today_average_roi': 0,
            'completed_signals_today': 0,
            'pending_signals_today': 0
        }


def _get_daily_performance_trends():
    """Get performance trends for the last 7 days (daily trading focus)"""
    try:
        trends = []
        for day in range(7):  # Last 7 days
            target_date = timezone.now().date() - timedelta(days=day)
            
            day_signals = TradingSignal.objects.filter(
                trading_session__date=target_date,
                generated_by='daily_trading_system'
            ).exclude(actual_outcome='pending')
            
            if day_signals.exists():
                profitable = day_signals.filter(actual_outcome='profitable').count()
                total = day_signals.count()
                accuracy = (profitable / total * 100) if total > 0 else 0
                
                # Calculate average ROI for the day
                total_roi = 0
                roi_count = 0
                for signal in day_signals:
                    roi = _calculate_signal_roi(signal)
                    if roi is not None:
                        total_roi += roi
                        roi_count += 1
                
                avg_roi = total_roi / roi_count if roi_count > 0 else 0
                
                trends.append({
                    'date': target_date.strftime('%Y-%m-%d'),
                    'day_name': target_date.strftime('%A'),
                    'accuracy': round(accuracy, 2),
                    'avg_roi': round(avg_roi, 2),
                    'total_signals': total,
                    'profitable_signals': profitable
                })
            else:
                trends.append({
                    'date': target_date.strftime('%Y-%m-%d'),
                    'day_name': target_date.strftime('%A'),
                    'accuracy': 0,
                    'avg_roi': 0,
                    'total_signals': 0,
                    'profitable_signals': 0
                })
        
        return trends
        
    except Exception as e:
        logger.error(f"Error getting daily performance trends: {e}")
        return []


def _calculate_type_accuracy(queryset):
    """Calculate accuracy for a specific signal type based on actual outcomes"""
    if not queryset.exists():
        return 0
    
    profitable = queryset.filter(actual_outcome='profitable').count()
    total = queryset.count()
    return (profitable / total * 100) if total > 0 else 0


def _calculate_signal_roi(signal):
    """Calculate ROI for a trading signal based on price movement"""
    try:
        if not signal.outcome_price or not signal.price_at_signal:
            return None
        
        price_at_signal = float(signal.price_at_signal)
        outcome_price = float(signal.outcome_price)
        
        # Prevent division by zero
        if price_at_signal == 0:
            return None
        
        # Calculate ROI based on signal type
        if signal.signal_type == 'buy':
            # For buy signals, positive ROI if price went up
            roi = ((outcome_price - price_at_signal) / price_at_signal) * 100
        elif signal.signal_type == 'sell':
            # For sell signals, positive ROI if price went down
            roi = ((price_at_signal - outcome_price) / price_at_signal) * 100
        else:  # hold
            # For hold signals, we consider it neutral
            roi = 0
        
        return roi
        
    except (ValueError, ZeroDivisionError, AttributeError, TypeError):
        return None


def _get_performance_trends():
    """Get performance trends over the last weeks"""
    try:
        trends = []
        for week in range(4):  # Last 4 weeks
            start_date = timezone.now() - timedelta(weeks=week+1)
            end_date = timezone.now() - timedelta(weeks=week)
            
            week_signals = TradingSignal.objects.filter(
                created_at__gte=start_date,
                created_at__lt=end_date
            ).exclude(outcome_price__isnull=True)
            
            if week_signals.exists():
                profitable = week_signals.filter(actual_outcome='profitable').count()
                total = week_signals.count()
                accuracy = (profitable / total * 100) if total > 0 else 0
                
                # Calculate average ROI for the week
                total_roi = 0
                roi_count = 0
                for signal in week_signals:
                    roi = _calculate_signal_roi(signal)
                    if roi is not None:
                        total_roi += roi
                        roi_count += 1
                
                avg_roi = total_roi / roi_count if roi_count > 0 else 0
            else:
                accuracy = 0
                avg_roi = 0
            
            trends.append({
                'week': f"Week {4-week}",
                'accuracy': round(accuracy, 2),
                'avg_roi': round(avg_roi, 2),
                'total_signals': week_signals.count() if week_signals.exists() else 0
            })
        
        return list(reversed(trends))  # Most recent last
        
    except Exception as e:
        print(f"Error getting performance trends: {e}")
        return []


def _get_learning_statistics():
    """Get statistics about model learning"""
    try:
        # Get prediction results that contributed to learning
        learning_predictions = PredictionResult.objects.filter(
            accuracy_score__isnull=False
        )
        
        total_learning_instances = learning_predictions.count()
        avg_accuracy_score = learning_predictions.aggregate(
            avg_score=Avg('accuracy_score')
        )['avg_score'] or 0
        
        # Count feedback instances
        feedback_count = learning_predictions.exclude(user_feedback__isnull=True).count()
        
        return {
            'total_learning_instances': total_learning_instances,
            'average_accuracy_score': round(float(avg_accuracy_score), 3),
            'feedback_instances': feedback_count,
            'learning_enabled': _is_learning_enabled()
        }
        
    except Exception as e:
        print(f"Error getting learning statistics: {e}")
        return {
            'total_learning_instances': 0,
            'average_accuracy_score': 0,
            'feedback_instances': 0,
            'learning_enabled': False
        }


def _is_learning_enabled():
    """Check if learning is currently enabled in config"""
    try:
        from pathlib import Path
        from django.conf import settings
        
        config_file = Path(settings.BASE_DIR) / 'ml_models' / 'ml_config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('enable_feedback', False)
        return False
    except:
        return False


def _analyze_signal_outcome(signal):
    """Analyze the outcome of a specific trading signal"""
    try:
        if not signal.outcome_price:
            return {
                'status': 'pending',
                'accuracy': None,
                'roi': None,
                'time_to_outcome': None
            }
        
        # Calculate time to outcome
        time_to_outcome = None
        if signal.outcome_date:
            time_diff = signal.outcome_date - signal.created_at
            time_to_outcome = time_diff.total_seconds() / 3600  # hours
        
        # Calculate ROI
        roi = _calculate_signal_roi(signal)
        
        # Determine if signal was accurate (profitable outcome)
        is_accurate = signal.actual_outcome == 'profitable'
        
        return {
            'status': 'completed',
            'accuracy': is_accurate,
            'roi': roi,
            'time_to_outcome': round(time_to_outcome, 1) if time_to_outcome else None,
            'outcome_price': float(signal.outcome_price) if signal.outcome_price else None,
            'predicted_price': float(signal.target_price) if signal.target_price else float(signal.price_at_signal)
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def _get_model_performance_history():
    """Get historical model performance data"""
    try:
        history = []
        for days_ago in range(30, 0, -5):  # Every 5 days for last 30 days
            date = timezone.now() - timedelta(days=days_ago)
            
            # Get signals up to this date with outcomes
            signals = TradingSignal.objects.filter(
                created_at__lte=date
            ).exclude(outcome_price__isnull=True)
            
            if signals.exists():
                profitable = signals.filter(actual_outcome='profitable').count()
                total = signals.count()
                accuracy = (profitable / total * 100) if total > 0 else 0
            else:
                accuracy = 0
            
            history.append({
                'date': date.strftime('%Y-%m-%d'),
                'accuracy': round(accuracy, 2),
                'total_samples': signals.count() if signals.exists() else 0
            })
        
        return history
        
    except Exception as e:
        print(f"Error getting performance history: {e}")
        return []


def _calculate_learning_effectiveness():
    """Calculate how effective the learning process has been"""
    try:
        # Compare performance before and after learning was enabled
        # Get recent performance (assuming learning is active)
        recent_accuracy = _calculate_accuracy_metrics()['overall_accuracy']
        
        # Get older performance (before learning)
        old_signals = TradingSignal.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=30)
        ).exclude(outcome_price__isnull=True)
        
        if old_signals.exists():
            old_profitable = old_signals.filter(actual_outcome='profitable').count()
            old_total = old_signals.count()
            old_accuracy = (old_profitable / old_total * 100) if old_total > 0 else 0
        else:
            old_accuracy = 0
        
        improvement = recent_accuracy - old_accuracy
        
        return {
            'recent_accuracy': recent_accuracy,
            'baseline_accuracy': round(old_accuracy, 2),
            'improvement': round(improvement, 2),
            'improvement_percentage': round((improvement / old_accuracy * 100) if old_accuracy > 0 else 0, 2)
        }
        
    except Exception as e:
        print(f"Error calculating learning effectiveness: {e}")
        return {
            'recent_accuracy': 0,
            'baseline_accuracy': 0,
            'improvement': 0,
            'improvement_percentage': 0
        }


def _analyze_feedback_contributions():
    """Analyze how different types of feedback contribute to learning"""
    try:
        # Get PredictionResult records with user feedback
        feedback_results = PredictionResult.objects.exclude(user_feedback__isnull=True).exclude(user_feedback={})
        
        # Analyze feedback based on actual accuracy scores
        positive_feedback = feedback_results.filter(accuracy_score__gte=0.7)  # Good predictions
        negative_feedback = feedback_results.filter(accuracy_score__lt=0.7)   # Poor predictions
        
        # Calculate impact
        positive_impact = positive_feedback.aggregate(avg_score=Avg('accuracy_score'))['avg_score'] or 0
        negative_impact = negative_feedback.aggregate(avg_score=Avg('accuracy_score'))['avg_score'] or 0
        
        return {
            'positive_feedback_count': positive_feedback.count(),
            'negative_feedback_count': negative_feedback.count(),
            'positive_avg_impact': round(float(positive_impact), 3),
            'negative_avg_impact': round(float(negative_impact), 3),
            'total_feedback_instances': feedback_results.count()
        }
        
    except Exception as e:
        print(f"Error analyzing feedback contributions: {e}")
        return {
            'positive_feedback_count': 0,
            'negative_feedback_count': 0,
            'positive_avg_impact': 0,
            'negative_avg_impact': 0,
            'total_feedback_instances': 0
        }


@login_required
def daily_trading_api(request):
    """
    API endpoint for daily trading recommendation data.
    Returns JSON data for AJAX calls from the dashboard.
    """
    try:
        # Initialize analyzers
        daily_analyzer = DailyTradingPerformanceAnalyzer()
        feedback_system = MLRecommendationFeedbackSystem()
        
        # Get request parameters
        trading_date_str = request.GET.get('date')
        if trading_date_str:
            trading_date = datetime.strptime(trading_date_str, '%Y-%m-%d').date()
        else:
            trading_date = timezone.now().date()
        
        action = request.GET.get('action', 'performance')
        
        if action == 'performance':
            # Get daily performance metrics
            daily_metrics = daily_analyzer.calculate_daily_performance(trading_date)
            hourly_breakdown = daily_analyzer.get_hourly_performance_breakdown(trading_date)
            
            response_data = {
                'trading_date': trading_date.isoformat(),
                'metrics': {
                    'total_signals': daily_metrics.total_signals,
                    'profitable_signals': daily_metrics.profitable_signals,
                    'loss_signals': daily_metrics.loss_signals,
                    'pending_signals': daily_metrics.pending_signals,
                    'win_rate': daily_metrics.win_rate,
                    'avg_return_per_hour': daily_metrics.avg_return_per_hour,
                    'total_return_today': daily_metrics.total_return_today,
                    'best_signal_return': daily_metrics.best_signal_return,
                    'worst_signal_return': daily_metrics.worst_signal_return,
                    'avg_signal_duration_hours': daily_metrics.avg_signal_duration_hours,
                    'signals_hit_target': daily_metrics.signals_hit_target,
                    'signals_hit_stop': daily_metrics.signals_hit_stop
                },
                'hourly_breakdown': [
                    {
                        'hour': h.hour,
                        'signals_generated': h.signals_generated,
                        'win_rate': h.win_rate,
                        'avg_return': h.avg_return,
                        'best_performer': h.best_performer,
                        'worst_performer': h.worst_performer
                    } for h in hourly_breakdown
                ]
            }
            
        elif action == 'feedback':
            # Get ML feedback data
            days_back = int(request.GET.get('days', 7))
            feedbacks = feedback_system.analyze_recommendation_quality(days_back=days_back)
            patterns = feedback_system.identify_performance_patterns(days_back=days_back*2)
            improvements = feedback_system.generate_improvement_recommendations(feedbacks, patterns)
            
            response_data = {
                'analysis_date': timezone.now().date().isoformat(),
                'days_analyzed': days_back,
                'feedbacks': [
                    {
                        'stock_symbol': f.stock_symbol,
                        'signal_type': f.signal_type,
                        'confidence_level': f.confidence_level,
                        'target_accuracy': f.target_accuracy,
                        'actual_accuracy': f.actual_accuracy,
                        'avg_roi': f.avg_roi,
                        'improvement_score': f.improvement_score,
                        'feedback_notes': f.feedback_notes
                    } for f in feedbacks[:20]  # Limit to top 20
                ],
                'patterns': [
                    {
                        'pattern_type': p.pattern_type,
                        'description': p.description,
                        'frequency': p.frequency,
                        'impact_score': p.impact_score,
                        'suggested_action': p.suggested_action
                    } for p in patterns
                ],
                'improvements': improvements
            }
            
        elif action == 'update_signals':
            # Update signal outcomes
            if request.method == 'POST':
                results = daily_analyzer.update_intraday_signal_outcomes()
                response_data = {
                    'success': True,
                    'message': 'Signals updated successfully',
                    'results': results
                }
            else:
                response_data = {
                    'error': 'POST method required for signal updates'
                }
                
        else:
            response_data = {
                'error': f'Unknown action: {action}'
            }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in daily trading API: {e}", exc_info=True)
        return JsonResponse({
            'error': f'API error: {str(e)}'
        }, status=500)


@login_required
def recommendation_quality_report(request):
    """
    Generate a detailed recommendation quality report.
    """
    try:
        feedback_system = MLRecommendationFeedbackSystem()
        
        # Get parameters
        days_back = int(request.GET.get('days', 30))
        format_type = request.GET.get('format', 'html')  # html or json
        
        # Generate comprehensive analysis
        feedbacks = feedback_system.analyze_recommendation_quality(days_back=days_back)
        patterns = feedback_system.identify_performance_patterns(days_back=days_back)
        improvements = feedback_system.generate_improvement_recommendations(feedbacks, patterns)
        
        # Calculate summary statistics
        total_analyzed = len(feedbacks)
        high_performers = len([f for f in feedbacks if f.actual_accuracy > 80])
        low_performers = len([f for f in feedbacks if f.actual_accuracy < 50])
        avg_accuracy = sum(f.actual_accuracy for f in feedbacks) / total_analyzed if feedbacks else 0
        avg_roi = sum(f.avg_roi for f in feedbacks) / total_analyzed if feedbacks else 0
        
        report_data = {
            'report_date': timezone.now().date(),
            'days_analyzed': days_back,
            'summary': {
                'total_analyzed': total_analyzed,
                'high_performers': high_performers,
                'low_performers': low_performers,
                'avg_accuracy': round(avg_accuracy, 2),
                'avg_roi': round(avg_roi, 2),
                'patterns_identified': len(patterns)
            },
            'feedbacks': feedbacks,
            'patterns': patterns,
            'improvements': improvements
        }
        
        if format_type == 'json':
            # Return JSON for API consumption
            json_data = {
                'report_date': report_data['report_date'].isoformat(),
                'days_analyzed': report_data['days_analyzed'],
                'summary': report_data['summary'],
                'feedbacks': [
                    {
                        'stock_symbol': f.stock_symbol,
                        'signal_type': f.signal_type,
                        'actual_accuracy': f.actual_accuracy,
                        'avg_roi': f.avg_roi,
                        'improvement_score': f.improvement_score,
                        'feedback_notes': f.feedback_notes
                    } for f in feedbacks
                ],
                'patterns': [
                    {
                        'pattern_type': p.pattern_type,
                        'description': p.description,
                        'frequency': p.frequency,
                        'impact_score': p.impact_score,
                        'suggested_action': p.suggested_action
                    } for p in patterns
                ],
                'improvements': improvements
            }
            return JsonResponse(json_data)
        else:
            # Return HTML template
            return render(request, 'analysis/recommendation_quality_report.html', {
                'report_data': report_data
            })
            
    except Exception as e:
        logger.error(f"Error generating recommendation quality report: {e}", exc_info=True)
        format_type = request.GET.get('format', 'html')  # Ensure format_type is defined
        if format_type == 'json':
            return JsonResponse({'error': str(e)}, status=500)
        else:
            return render(request, 'analysis/recommendation_quality_report.html', {
                'error': str(e)
            })
