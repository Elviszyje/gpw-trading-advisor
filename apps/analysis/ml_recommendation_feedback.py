"""
ML Recommendation Feedback System
Analyzes recommendation performance and provides feedback to improve future recommendations
"""
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from django.db.models import QuerySet, Avg, Count, Q, Sum
from django.utils import timezone
from dataclasses import dataclass
import json

from apps.analysis.models import TradingSignal, StockData, TradingSession
from apps.analysis.daily_trading_performance import DailyTradingPerformanceAnalyzer
from apps.core.models import StockSymbol

import logging
logger = logging.getLogger(__name__)


@dataclass 
class RecommendationFeedback:
    """Container for recommendation feedback metrics."""
    stock_symbol: str
    signal_type: str
    confidence_level: float
    target_accuracy: float
    actual_accuracy: float
    avg_roi: float
    improvement_score: float
    feedback_notes: str


@dataclass
class PerformancePattern:
    """Pattern in recommendation performance."""
    pattern_type: str
    description: str
    frequency: int
    impact_score: float
    suggested_action: str


class MLRecommendationFeedbackSystem:
    """
    Analyzes recommendation performance and provides ML feedback.
    Tracks which types of recommendations work best and provides insights for improvement.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.analyzer = DailyTradingPerformanceAnalyzer()
    
    def analyze_recommendation_quality(
        self,
        days_back: int = 7,
        min_signals_threshold: int = 5
    ) -> List[RecommendationFeedback]:
        """
        Analyze recommendation quality by stock and signal type.
        
        Args:
            days_back: Number of days to analyze
            min_signals_threshold: Minimum number of signals required for analysis
            
        Returns:
            List of RecommendationFeedback objects
        """
        feedbacks = []
        
        # Get date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get all stocks with signals in the period
        stocks_with_signals = TradingSignal.objects.filter(
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system'
        ).values_list('stock__symbol', flat=True).distinct()
        
        for symbol in stocks_with_signals:
            # Analyze each signal type for this stock
            for signal_type in ['buy', 'sell', 'hold']:
                feedback = self._analyze_stock_signal_performance(
                    symbol, signal_type, start_date, end_date, min_signals_threshold
                )
                if feedback:
                    feedbacks.append(feedback)
        
        # Sort by improvement score (worst performing first)
        feedbacks.sort(key=lambda x: x.improvement_score)
        
        return feedbacks
    
    def identify_performance_patterns(
        self,
        days_back: int = 30
    ) -> List[PerformancePattern]:
        """
        Identify patterns in recommendation performance.
        """
        patterns = []
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get all signals in the period
        signals = TradingSignal.objects.filter(
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system'
        ).exclude(actual_outcome='pending')
        
        # Pattern 1: Time-of-day performance
        time_patterns = self._analyze_time_patterns(signals)
        patterns.extend(time_patterns)
        
        # Pattern 2: Confidence level vs accuracy
        confidence_patterns = self._analyze_confidence_patterns(signals)
        patterns.extend(confidence_patterns)
        
        # Pattern 3: Signal type performance by stock sector
        sector_patterns = self._analyze_sector_patterns(signals)
        patterns.extend(sector_patterns)
        
        # Pattern 4: Target price accuracy
        target_patterns = self._analyze_target_price_patterns(signals)
        patterns.extend(target_patterns)
        
        return patterns
    
    def generate_improvement_recommendations(
        self,
        feedbacks: List[RecommendationFeedback],
        patterns: List[PerformancePattern]
    ) -> Dict[str, Any]:
        """
        Generate actionable improvement recommendations based on analysis.
        """
        improvements = {
            'critical_issues': [],
            'optimization_opportunities': [],
            'model_adjustments': [],
            'strategy_changes': []
        }
        
        # Analyze critical issues (accuracy < 40%)
        critical_feedbacks = [f for f in feedbacks if f.actual_accuracy < 40]
        for feedback in critical_feedbacks:
            improvements['critical_issues'].append({
                'issue': f"Low accuracy for {feedback.stock_symbol} {feedback.signal_type} signals",
                'accuracy': feedback.actual_accuracy,
                'recommendation': f"Consider reducing confidence or avoiding {feedback.signal_type} signals for {feedback.stock_symbol}"
            })
        
        # Optimization opportunities (accuracy 60-80%)
        optimization_feedbacks = [f for f in feedbacks if 60 <= f.actual_accuracy <= 80]
        for feedback in optimization_feedbacks:
            improvements['optimization_opportunities'].append({
                'opportunity': f"Moderate performance for {feedback.stock_symbol} {feedback.signal_type}",
                'accuracy': feedback.actual_accuracy,
                'suggestion': f"Fine-tune parameters for {feedback.signal_type} signals on {feedback.stock_symbol}"
            })
        
        # Model adjustments based on patterns
        for pattern in patterns:
            if pattern.impact_score > 0.3:  # Significant impact
                improvements['model_adjustments'].append({
                    'pattern': pattern.description,
                    'impact': pattern.impact_score,
                    'action': pattern.suggested_action
                })
        
        # Strategy changes
        high_roi_feedbacks = [f for f in feedbacks if f.avg_roi > 2.0 and f.actual_accuracy > 70]
        for feedback in high_roi_feedbacks:
            improvements['strategy_changes'].append({
                'strategy': f"Increase allocation to {feedback.stock_symbol} {feedback.signal_type} signals",
                'rationale': f"High ROI ({feedback.avg_roi}%) with good accuracy ({feedback.actual_accuracy}%)"
            })
        
        return improvements
    
    def store_feedback_for_ml(
        self,
        feedbacks: List[RecommendationFeedback],
        patterns: List[PerformancePattern]
    ) -> Dict[str, int]:
        """
        Store feedback data in a format that can be used by ML models.
        """
        stored_count = 0
        error_count = 0
        
        for feedback in feedbacks:
            try:
                # Create or update feedback record
                feedback_data = {
                    'stock_symbol': feedback.stock_symbol,
                    'signal_type': feedback.signal_type,
                    'analysis_date': timezone.now().date().isoformat(),
                    'confidence_level': feedback.confidence_level,
                    'target_accuracy': feedback.target_accuracy,
                    'actual_accuracy': feedback.actual_accuracy,
                    'avg_roi': feedback.avg_roi,
                    'improvement_score': feedback.improvement_score,
                    'feedback_notes': feedback.feedback_notes
                }
                
                # Here you would typically store this in a dedicated FeedbackStorage model
                # For now, we'll log it and could store in a JSON field or separate table
                self.logger.info(f"ML Feedback stored: {json.dumps(feedback_data)}")
                stored_count += 1
                
            except Exception as e:
                self.logger.error(f"Error storing feedback for {feedback.stock_symbol}: {e}")
                error_count += 1
        
        return {
            'stored': stored_count,
            'errors': error_count
        }
    
    def _analyze_stock_signal_performance(
        self,
        symbol: str,
        signal_type: str,
        start_date: date,
        end_date: date,
        min_threshold: int
    ) -> Optional[RecommendationFeedback]:
        """Analyze performance for specific stock and signal type."""
        
        signals = TradingSignal.objects.filter(
            stock__symbol=symbol,
            signal_type=signal_type,
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system'
        ).exclude(actual_outcome='pending')
        
        if signals.count() < min_threshold:
            return None
        
        # Calculate metrics
        total_signals = signals.count()
        profitable_signals = signals.filter(actual_outcome='profitable').count()
        accuracy = (profitable_signals / total_signals * 100) if total_signals > 0 else 0
        
        # Calculate average ROI
        total_roi = 0
        roi_count = 0
        avg_confidence = 0
        
        for signal in signals:
            roi = self._calculate_roi(signal)
            if roi is not None:
                total_roi += roi
                roi_count += 1
            avg_confidence += float(signal.confidence)
        
        avg_roi = total_roi / roi_count if roi_count > 0 else 0
        avg_confidence = avg_confidence / total_signals if total_signals > 0 else 0
        
        # Calculate improvement score (lower is worse)
        target_accuracy = 70.0  # Target accuracy
        improvement_score = accuracy - target_accuracy
        
        # Generate feedback notes
        if accuracy < 50:
            notes = f"Poor performance - consider avoiding {signal_type} for {symbol}"
        elif accuracy < 70:
            notes = f"Below target - review {signal_type} criteria for {symbol}"
        else:
            notes = f"Good performance - maintain current approach for {symbol}"
        
        return RecommendationFeedback(
            stock_symbol=symbol,
            signal_type=signal_type,
            confidence_level=avg_confidence,
            target_accuracy=target_accuracy,
            actual_accuracy=round(accuracy, 2),
            avg_roi=round(avg_roi, 2),
            improvement_score=round(improvement_score, 2),
            feedback_notes=notes
        )
    
    def _analyze_time_patterns(self, signals: QuerySet) -> List[PerformancePattern]:
        """Analyze performance patterns by time of day."""
        patterns = []
        
        # Group by hour of signal creation
        hourly_performance = {}
        
        for signal in signals:
            hour = signal.created_at.hour
            if hour not in hourly_performance:
                hourly_performance[hour] = {'total': 0, 'profitable': 0}
            
            hourly_performance[hour]['total'] += 1
            if signal.actual_outcome == 'profitable':
                hourly_performance[hour]['profitable'] += 1
        
        # Find patterns
        for hour, data in hourly_performance.items():
            if data['total'] >= 5:  # Minimum signals for pattern
                accuracy = (data['profitable'] / data['total']) * 100
                
                if accuracy < 40:
                    patterns.append(PerformancePattern(
                        pattern_type='time_poor',
                        description=f"Poor performance at {hour}:00 ({accuracy:.1f}% accuracy)",
                        frequency=data['total'],
                        impact_score=0.8,
                        suggested_action=f"Reduce signal generation at {hour}:00 or review criteria"
                    ))
                elif accuracy > 80:
                    patterns.append(PerformancePattern(
                        pattern_type='time_excellent',
                        description=f"Excellent performance at {hour}:00 ({accuracy:.1f}% accuracy)",
                        frequency=data['total'],
                        impact_score=0.7,
                        suggested_action=f"Increase signal generation at {hour}:00"
                    ))
        
        return patterns
    
    def _analyze_confidence_patterns(self, signals: QuerySet) -> List[PerformancePattern]:
        """Analyze relationship between confidence levels and accuracy."""
        patterns = []
        
        # Group by confidence ranges
        confidence_ranges = {
            'low': (0, 60),
            'medium': (60, 80),
            'high': (80, 100)
        }
        
        for range_name, (min_conf, max_conf) in confidence_ranges.items():
            range_signals = signals.filter(
                confidence__gte=min_conf,
                confidence__lt=max_conf
            )
            
            if range_signals.count() >= 5:
                total = range_signals.count()
                profitable = range_signals.filter(actual_outcome='profitable').count()
                accuracy = (profitable / total) * 100
                
                expected_accuracy = min_conf + (max_conf - min_conf) / 2  # Expected based on confidence
                
                if accuracy < expected_accuracy - 15:  # Significantly underperforming
                    patterns.append(PerformancePattern(
                        pattern_type='confidence_mismatch',
                        description=f"{range_name.title()} confidence signals underperforming ({accuracy:.1f}% vs {expected_accuracy:.1f}% expected)",
                        frequency=total,
                        impact_score=0.6,
                        suggested_action=f"Calibrate confidence levels for {range_name} confidence range"
                    ))
        
        return patterns
    
    def _analyze_sector_patterns(self, signals: QuerySet) -> List[PerformancePattern]:
        """Analyze performance patterns by stock sector (placeholder - would need sector data)."""
        # This would require sector information in the stock data
        # For now, return empty patterns
        return []
    
    def _analyze_target_price_patterns(self, signals: QuerySet) -> List[PerformancePattern]:
        """Analyze accuracy of target price predictions."""
        patterns = []
        
        signals_with_targets = signals.filter(target_price__isnull=False)
        
        target_hit_count = 0
        total_with_targets = signals_with_targets.count()
        
        for signal in signals_with_targets:
            if signal.actual_outcome == 'profitable':
                # Assume profitable signals hit their targets
                target_hit_count += 1
        
        if total_with_targets >= 10:
            target_accuracy = (target_hit_count / total_with_targets) * 100
            
            if target_accuracy < 50:
                patterns.append(PerformancePattern(
                    pattern_type='target_price_poor',
                    description=f"Low target price accuracy ({target_accuracy:.1f}%)",
                    frequency=total_with_targets,
                    impact_score=0.5,
                    suggested_action="Review target price calculation methodology"
                ))
        
        return patterns
    
    def _calculate_roi(self, signal: TradingSignal) -> Optional[float]:
        """Calculate ROI for a signal."""
        try:
            if not signal.outcome_price or not signal.price_at_signal:
                return None
            
            entry_price = float(signal.price_at_signal)
            exit_price = float(signal.outcome_price)
            
            if entry_price == 0:
                return None
            
            if signal.signal_type == 'buy':
                roi = ((exit_price - entry_price) / entry_price) * 100
            elif signal.signal_type == 'sell':
                roi = ((entry_price - exit_price) / entry_price) * 100
            else:
                roi = 0
            
            return roi
            
        except (ValueError, ZeroDivisionError, AttributeError, TypeError):
            return None
