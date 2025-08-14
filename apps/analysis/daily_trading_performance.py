"""
Daily Trading Performance Tracking System
Specialized for intraday trading signals and hour-based evaluation
"""
from datetime import datetime, timedelta, time
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from django.db.models import QuerySet, Avg, Count, Q, Sum, Case, When, DecimalField
from django.utils import timezone
from dataclasses import dataclass

from apps.analysis.models import TradingSignal, StockData, TradingSession
from apps.core.models import StockSymbol

import logging

logger = logging.getLogger(__name__)

# Warsaw Stock Exchange trading hours (CET/CEST)
MARKET_OPEN_TIME = time(9, 0)  # 9:00 AM
MARKET_CLOSE_TIME = time(17, 0)  # 5:00 PM


@dataclass
class DailyTradingMetrics:
    """Container for daily trading performance metrics."""
    total_signals: int
    profitable_signals: int
    loss_signals: int
    pending_signals: int
    win_rate: float
    avg_return_per_hour: float
    total_return_today: float
    best_signal_return: float
    worst_signal_return: float
    avg_signal_duration_hours: float
    signals_hit_target: int
    signals_hit_stop: int


@dataclass
class HourlyPerformanceBreakdown:
    """Hourly performance breakdown for intraday analysis."""
    hour: int
    signals_generated: int
    win_rate: float
    avg_return: float
    best_performer: str
    worst_performer: str


class DailyTradingPerformanceAnalyzer:
    """
    Performance analyzer specialized for daily trading strategies.
    Focuses on intraday signals that should be resolved within the same trading session.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_daily_performance(
        self,
        trading_date: Optional[datetime.date] = None,
        stock_symbol: Optional[str] = None
    ) -> DailyTradingMetrics:
        """
        Calculate performance metrics for daily trading signals.
        
        Args:
            trading_date: Specific trading date to analyze (default: today)
            stock_symbol: Filter by specific stock symbol (optional)
            
        Returns:
            DailyTradingMetrics with intraday performance data
        """
        if trading_date is None:
            trading_date = timezone.now().date()
        
        # Get today's trading session
        try:
            trading_session = TradingSession.objects.get(date=trading_date)
        except TradingSession.DoesNotExist:
            return self._empty_metrics()
        
        # Base queryset for today's signals
        signals = TradingSignal.objects.filter(
            trading_session=trading_session,
            generated_by='daily_trading_system'
        ).select_related('stock', 'trading_session')
        
        if stock_symbol:
            signals = signals.filter(stock__symbol=stock_symbol)
        
        # Calculate basic counts
        total_signals = signals.count()
        profitable_signals = signals.filter(actual_outcome='profitable').count()
        loss_signals = signals.filter(actual_outcome='loss').count()
        pending_signals = signals.filter(actual_outcome='pending').count()
        
        # Calculate win rate for completed signals
        completed_signals = profitable_signals + loss_signals
        win_rate = (profitable_signals / completed_signals * 100) if completed_signals > 0 else 0.0
        
        # Calculate intraday returns
        returns_data = self._calculate_intraday_returns(signals)
        
        # Calculate signal durations and target/stop hit rates
        duration_data = self._calculate_signal_durations(signals)
        target_stop_data = self._calculate_target_stop_hits(signals)
        
        return DailyTradingMetrics(
            total_signals=total_signals,
            profitable_signals=profitable_signals,
            loss_signals=loss_signals,
            pending_signals=pending_signals,
            win_rate=win_rate,
            avg_return_per_hour=returns_data['avg_return_per_hour'],
            total_return_today=returns_data['total_return'],
            best_signal_return=returns_data['best_return'],
            worst_signal_return=returns_data['worst_return'],
            avg_signal_duration_hours=duration_data['avg_duration_hours'],
            signals_hit_target=target_stop_data['hit_target'],
            signals_hit_stop=target_stop_data['hit_stop']
        )
    
    def get_hourly_performance_breakdown(
        self,
        trading_date: Optional[datetime.date] = None
    ) -> List[HourlyPerformanceBreakdown]:
        """Get performance breakdown by trading hour."""
        if trading_date is None:
            trading_date = timezone.now().date()
        
        breakdowns = []
        
        # Analyze each trading hour (9 AM to 5 PM)
        for hour in range(9, 17):
            hour_start = timezone.make_aware(
                datetime.combine(trading_date, time(hour, 0))
            )
            hour_end = timezone.make_aware(
                datetime.combine(trading_date, time(hour, 59, 59))
            )
            
            hour_signals = TradingSignal.objects.filter(
                created_at__range=[hour_start, hour_end],
                generated_by='daily_trading_system'
            ).select_related('stock')
            
            if hour_signals.exists():
                # Calculate hourly metrics
                completed = hour_signals.exclude(actual_outcome='pending')
                profitable = completed.filter(actual_outcome='profitable')
                
                win_rate = (profitable.count() / completed.count() * 100) if completed.exists() else 0
                
                # Calculate average return for this hour
                returns = []
                best_symbol = ""
                worst_symbol = ""
                best_return = float('-inf')
                worst_return = float('inf')
                
                for signal in completed:
                    roi = self._calculate_signal_roi(signal)
                    if roi is not None:
                        returns.append(roi)
                        if roi > best_return:
                            best_return = roi
                            best_symbol = signal.stock.symbol
                        if roi < worst_return:
                            worst_return = roi
                            worst_symbol = signal.stock.symbol
                
                avg_return = sum(returns) / len(returns) if returns else 0
                
                breakdown = HourlyPerformanceBreakdown(
                    hour=hour,
                    signals_generated=hour_signals.count(),
                    win_rate=round(win_rate, 2),
                    avg_return=round(avg_return, 2),
                    best_performer=f"{best_symbol} ({best_return:.2f}%)" if best_symbol else "N/A",
                    worst_performer=f"{worst_symbol} ({worst_return:.2f}%)" if worst_symbol else "N/A"
                )
                breakdowns.append(breakdown)
        
        return breakdowns
    
    def update_intraday_signal_outcomes(self) -> Dict[str, int]:
        """
        Update outcomes for signals generated today based on current market data.
        Only evaluates signals within the same trading session.
        """
        updated_count = 0
        error_count = 0
        
        today = timezone.now().date()
        
        try:
            trading_session = TradingSession.objects.get(date=today)
        except TradingSession.DoesNotExist:
            return {'updated': 0, 'errors': 0, 'processed': 0}
        
        # Get today's pending signals
        pending_signals = TradingSignal.objects.filter(
            trading_session=trading_session,
            actual_outcome='pending',
            generated_by='daily_trading_system'
        ).select_related('stock', 'trading_session')
        
        current_time = timezone.now().time()
        
        for signal in pending_signals:
            try:
                # For daily trading, evaluate based on:
                # 1. Current price vs entry price
                # 2. Target/stop loss hits during the day
                # 3. End of day evaluation if market is closed
                
                outcome = self._determine_intraday_outcome(signal, current_time)
                if outcome:
                    signal.update_outcome(
                        outcome['result'],
                        outcome['price'],
                        outcome['date']
                    )
                    updated_count += 1
                    self.logger.info(f"Updated intraday signal outcome for {signal.stock.symbol}: {outcome['result']}")
                    
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error updating intraday signal {signal.pk}: {str(e)}")
        
        return {
            'updated': updated_count,
            'errors': error_count,
            'processed': pending_signals.count()
        }
    
    def _determine_intraday_outcome(
        self,
        signal: TradingSignal,
        current_time: time
    ) -> Optional[Dict[str, Any]]:
        """
        Determine signal outcome within the same trading day.
        """
        try:
            # Get today's price data for this stock
            today_data = StockData.objects.filter(
                stock=signal.stock,
                trading_session=signal.trading_session
            ).first()
            
            if not today_data:
                return None
            
            entry_price = signal.price_at_signal
            target_price = signal.target_price
            stop_loss_price = signal.stop_loss_price
            
            # Check if target or stop loss was hit based on high/low
            if signal.signal_type == 'buy':
                # For buy signals
                if target_price and today_data.high_price and today_data.high_price >= target_price:
                    return {
                        'result': 'profitable',
                        'price': target_price,
                        'date': timezone.now()
                    }
                elif stop_loss_price and today_data.low_price and today_data.low_price <= stop_loss_price:
                    return {
                        'result': 'loss',
                        'price': stop_loss_price,
                        'date': timezone.now()
                    }
            
            elif signal.signal_type == 'sell':
                # For sell signals  
                if target_price and today_data.low_price and today_data.low_price <= target_price:
                    return {
                        'result': 'profitable',
                        'price': target_price,
                        'date': timezone.now()
                    }
                elif stop_loss_price and today_data.high_price and today_data.high_price >= stop_loss_price:
                    return {
                        'result': 'loss',
                        'price': stop_loss_price,
                        'date': timezone.now()
                    }
            
            # If market is closed (after 5 PM), evaluate based on closing price
            if current_time >= MARKET_CLOSE_TIME:
                if today_data.close_price:
                    close_price = today_data.close_price
                    
                    if signal.signal_type == 'buy':
                        result = 'profitable' if close_price > entry_price else 'loss'
                    elif signal.signal_type == 'sell':
                        result = 'profitable' if close_price < entry_price else 'loss'
                    else:
                        result = 'break_even'
                    
                    return {
                        'result': result,
                        'price': close_price,
                        'date': timezone.now()
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error determining intraday outcome for signal {signal.pk}: {str(e)}")
            return None
    
    def _calculate_intraday_returns(self, signals: QuerySet) -> Dict[str, Any]:
        """Calculate return metrics for intraday signals."""
        returns = []
        
        completed_signals = signals.exclude(actual_outcome='pending')
        
        for signal in completed_signals:
            roi = self._calculate_signal_roi(signal)
            if roi is not None:
                returns.append(roi)
        
        if not returns:
            return {
                'avg_return_per_hour': 0.0,
                'total_return': 0.0,
                'best_return': 0.0,
                'worst_return': 0.0
            }
        
        total_return = sum(returns)
        best_return = max(returns)
        worst_return = min(returns)
        
        # Calculate average return per hour (assuming 8-hour trading day)
        avg_return_per_hour = total_return / 8 if returns else 0
        
        return {
            'avg_return_per_hour': round(avg_return_per_hour, 2),
            'total_return': round(total_return, 2),
            'best_return': round(best_return, 2),
            'worst_return': round(worst_return, 2)
        }
    
    def _calculate_signal_roi(self, signal: TradingSignal) -> Optional[float]:
        """Calculate ROI for a trading signal."""
        try:
            if not signal.outcome_price or not signal.price_at_signal:
                return None
            
            entry_price = float(signal.price_at_signal)
            exit_price = float(signal.outcome_price)
            
            if entry_price == 0:
                return None
            
            # Calculate ROI based on signal type
            if signal.signal_type == 'buy':
                roi = ((exit_price - entry_price) / entry_price) * 100
            elif signal.signal_type == 'sell':
                roi = ((entry_price - exit_price) / entry_price) * 100
            else:
                roi = 0
            
            return roi
            
        except (ValueError, ZeroDivisionError, AttributeError, TypeError):
            return None
    
    def _calculate_signal_durations(self, signals: QuerySet) -> Dict[str, float]:
        """Calculate average signal duration in hours."""
        durations = []
        
        completed_signals = signals.exclude(actual_outcome='pending').exclude(outcome_date__isnull=True)
        
        for signal in completed_signals:
            if signal.outcome_date:
                duration = (signal.outcome_date - signal.created_at).total_seconds() / 3600  # hours
                durations.append(duration)
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'avg_duration_hours': round(avg_duration, 2)
        }
    
    def _calculate_target_stop_hits(self, signals: QuerySet) -> Dict[str, int]:
        """Calculate how many signals hit target vs stop loss."""
        hit_target = 0
        hit_stop = 0
        
        completed_signals = signals.exclude(actual_outcome='pending')
        
        for signal in completed_signals:
            if signal.actual_outcome == 'profitable':
                # Assume profitable signals hit target
                hit_target += 1
            elif signal.actual_outcome == 'loss':
                # Assume loss signals hit stop loss
                hit_stop += 1
        
        return {
            'hit_target': hit_target,
            'hit_stop': hit_stop
        }
    
    def _empty_metrics(self) -> DailyTradingMetrics:
        """Return empty metrics when no data available."""
        return DailyTradingMetrics(
            total_signals=0,
            profitable_signals=0,
            loss_signals=0,
            pending_signals=0,
            win_rate=0.0,
            avg_return_per_hour=0.0,
            total_return_today=0.0,
            best_signal_return=0.0,
            worst_signal_return=0.0,
            avg_signal_duration_hours=0.0,
            signals_hit_target=0,
            signals_hit_stop=0
        )
