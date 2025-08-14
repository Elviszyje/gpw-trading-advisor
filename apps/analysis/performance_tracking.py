"""
Signal Performance Tracking System
Provides comprehensive analysis of trading signal effectiveness
"""
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from django.db.models import QuerySet, Avg, Count, Q, Sum, Case, When, DecimalField
from django.utils import timezone
from dataclasses import dataclass

from apps.analysis.models import TradingSignal, StockData
from apps.core.models import StockSymbol
from apps.scrapers.models import NewsArticleModel
from apps.core.models import NewsClassification, StockSentiment

import logging

logger = logging.getLogger(__name__)


@dataclass
class SignalPerformanceMetrics:
    """Container for signal performance metrics."""
    total_signals: int
    profitable_signals: int
    loss_signals: int
    pending_signals: int
    win_rate: float
    avg_return: float
    total_return: float
    sharpe_ratio: Optional[float]
    max_drawdown: float
    best_signal_return: float
    worst_signal_return: float
    # Enhanced metrics for news impact analysis
    signals_with_news: int = 0
    signals_without_news: int = 0
    news_boosted_signals: int = 0
    news_penalty_signals: int = 0
    avg_return_with_positive_news: float = 0.0
    avg_return_with_negative_news: float = 0.0
    avg_return_no_news: float = 0.0


@dataclass
class StockPerformanceBreakdown:
    """Performance breakdown by stock symbol."""
    symbol: str
    total_signals: int
    win_rate: float
    avg_return: float
    total_return: float
    best_return: float
    worst_return: float
    # Enhanced with news analysis
    signals_with_news: int = 0
    avg_news_sentiment: float = 0.0
    news_impact_correlation: float = 0.0


class SignalPerformanceAnalyzer:
    """
    Comprehensive signal performance analysis system.
    Tracks accuracy, ROI, win/loss ratios, and provides detailed breakdowns.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_signal_performance(
        self, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        stock_symbol: Optional[str] = None
    ) -> SignalPerformanceMetrics:
        """
        Calculate comprehensive performance metrics for trading signals.
        
        Args:
            start_date: Start date for analysis (default: 30 days ago)
            end_date: End date for analysis (default: today)
            stock_symbol: Filter by specific stock symbol (optional)
            
        Returns:
            SignalPerformanceMetrics with all calculated metrics
        """
        if start_date is None:
            start_date = (timezone.now() - timedelta(days=30)).date()
        if end_date is None:
            end_date = timezone.now().date()
        
        # Base queryset for signals
        signals = TradingSignal.objects.filter(
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system'
        ).select_related('stock', 'trading_session')
        
        if stock_symbol:
            signals = signals.filter(stock__symbol=stock_symbol)
        
        # Calculate basic counts
        total_signals = signals.count()
        profitable_signals = signals.filter(actual_outcome='profitable').count()
        loss_signals = signals.filter(actual_outcome='loss').count()
        pending_signals = signals.filter(actual_outcome='pending').count()
        
        # Calculate win rate
        completed_signals = profitable_signals + loss_signals
        win_rate = (profitable_signals / completed_signals * 100) if completed_signals > 0 else 0.0
        
        # Calculate returns
        returns_data = self._calculate_signal_returns(signals.filter(actual_outcome__in=['profitable', 'loss']))
        
        return SignalPerformanceMetrics(
            total_signals=total_signals,
            profitable_signals=profitable_signals,
            loss_signals=loss_signals,
            pending_signals=pending_signals,
            win_rate=win_rate,
            avg_return=returns_data['avg_return'],
            total_return=returns_data['total_return'],
            sharpe_ratio=returns_data['sharpe_ratio'],
            max_drawdown=returns_data['max_drawdown'],
            best_signal_return=returns_data['best_return'],
            worst_signal_return=returns_data['worst_return']
        )
    
    def analyze_news_impact_on_performance(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Analyze how news sentiment correlates with trading signal performance.
        
        Returns comprehensive analysis of news impact on signal accuracy and ROI.
        """
        if start_date is None:
            start_date = (timezone.now() - timedelta(days=30)).date()
        if end_date is None:
            end_date = timezone.now().date()
        
        # Get all completed signals in the period
        signals = TradingSignal.objects.filter(
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system',
            actual_outcome__in=['profitable', 'loss']
        ).select_related('stock', 'trading_session')
        
        signals_with_news = []
        signals_without_news = []
        news_sentiment_correlation = []
        
        for signal in signals:
            # Check for news around signal date
            news_start = signal.trading_session.date - timedelta(days=2)
            news_end = signal.trading_session.date + timedelta(days=1)
            
            # Find relevant news
            relevant_news = NewsArticleModel.objects.filter(
                stock_symbols__contains=[signal.stock.symbol],
                published_date__date__range=[news_start, news_end]
            ).prefetch_related('ai_classification')
            
            roi = self.calculate_roi_per_signal(signal)
            if roi is None:
                continue
                
            if relevant_news.exists():
                # Calculate average sentiment for this stock around signal time
                sentiments = []
                
                for news in relevant_news:
                    try:
                        # Try to get stock-specific sentiment first
                        stock_sentiment = StockSentiment.objects.get(
                            classification__article=news,
                            stock=signal.stock
                        )
                        sentiments.append(float(stock_sentiment.sentiment_score))
                    except StockSentiment.DoesNotExist:
                        # Fall back to general news sentiment
                        try:
                            classification = NewsClassification.objects.get(article=news)
                            if classification.sentiment_score is not None:
                                sentiments.append(float(classification.sentiment_score))
                        except NewsClassification.DoesNotExist:
                            continue
                
                if sentiments:
                    avg_sentiment = sum(sentiments) / len(sentiments)
                    
                    signals_with_news.append({
                        'signal': signal,
                        'roi': roi,
                        'sentiment': avg_sentiment,
                        'news_count': len(relevant_news),
                        'signal_type': signal.signal_type,
                        'confidence': float(signal.confidence) if signal.confidence else 0,
                        'outcome': signal.actual_outcome
                    })
                    
                    news_sentiment_correlation.append((avg_sentiment, roi))
                else:
                    signals_without_news.append({
                        'signal': signal,
                        'roi': roi,
                        'signal_type': signal.signal_type,
                        'outcome': signal.actual_outcome
                    })
            else:
                signals_without_news.append({
                    'signal': signal,
                    'roi': roi,
                    'signal_type': signal.signal_type,
                    'outcome': signal.actual_outcome
                })
        
        # Calculate statistics
        analysis_results = {
            'period': f"{start_date} to {end_date}",
            'total_analyzed_signals': len(signals_with_news) + len(signals_without_news),
            'signals_with_news': len(signals_with_news),
            'signals_without_news': len(signals_without_news),
            'news_coverage': len(signals_with_news) / (len(signals_with_news) + len(signals_without_news)) * 100 if (len(signals_with_news) + len(signals_without_news)) > 0 else 0,
        }
        
        # Performance with news
        if signals_with_news:
            positive_news_signals = [s for s in signals_with_news if s['sentiment'] > 0.1]
            negative_news_signals = [s for s in signals_with_news if s['sentiment'] < -0.1]
            neutral_news_signals = [s for s in signals_with_news if -0.1 <= s['sentiment'] <= 0.1]
            
            analysis_results.update({
                'with_news_avg_roi': sum(s['roi'] for s in signals_with_news) / len(signals_with_news),
                'with_news_win_rate': len([s for s in signals_with_news if s['roi'] > 0]) / len(signals_with_news) * 100,
                'positive_news_count': len(positive_news_signals),
                'positive_news_avg_roi': sum(s['roi'] for s in positive_news_signals) / len(positive_news_signals) if positive_news_signals else 0,
                'positive_news_win_rate': len([s for s in positive_news_signals if s['roi'] > 0]) / len(positive_news_signals) * 100 if positive_news_signals else 0,
                'negative_news_count': len(negative_news_signals),
                'negative_news_avg_roi': sum(s['roi'] for s in negative_news_signals) / len(negative_news_signals) if negative_news_signals else 0,
                'negative_news_win_rate': len([s for s in negative_news_signals if s['roi'] > 0]) / len(negative_news_signals) * 100 if negative_news_signals else 0,
                'neutral_news_count': len(neutral_news_signals),
                'neutral_news_avg_roi': sum(s['roi'] for s in neutral_news_signals) / len(neutral_news_signals) if neutral_news_signals else 0,
            })
        
        # Performance without news  
        if signals_without_news:
            analysis_results.update({
                'without_news_avg_roi': sum(s['roi'] for s in signals_without_news) / len(signals_without_news),
                'without_news_win_rate': len([s for s in signals_without_news if s['roi'] > 0]) / len(signals_without_news) * 100,
            })
        
        # Correlation analysis
        if len(news_sentiment_correlation) > 3:
            sentiments, rois = zip(*news_sentiment_correlation)
            
            # Simple correlation coefficient
            n = len(sentiments)
            sentiment_mean = sum(sentiments) / n
            roi_mean = sum(rois) / n
            
            numerator = sum((s - sentiment_mean) * (r - roi_mean) for s, r in zip(sentiments, rois))
            sentiment_var = sum((s - sentiment_mean) ** 2 for s in sentiments)
            roi_var = sum((r - roi_mean) ** 2 for r in rois)
            
            if sentiment_var > 0 and roi_var > 0:
                correlation = numerator / (sentiment_var * roi_var) ** 0.5
                analysis_results['sentiment_roi_correlation'] = correlation
            else:
                analysis_results['sentiment_roi_correlation'] = 0.0
        else:
            analysis_results['sentiment_roi_correlation'] = 0.0
        
        # Key insights
        insights = []
        
        if analysis_results.get('positive_news_avg_roi', 0) > analysis_results.get('without_news_avg_roi', 0):
            improvement = analysis_results['positive_news_avg_roi'] - analysis_results.get('without_news_avg_roi', 0)
            insights.append(f"Positive news improves ROI by {improvement:.2f}% on average")
        
        if analysis_results.get('negative_news_avg_roi', 0) < analysis_results.get('without_news_avg_roi', 0):
            degradation = analysis_results.get('without_news_avg_roi', 0) - analysis_results['negative_news_avg_roi']
            insights.append(f"Negative news reduces ROI by {degradation:.2f}% on average")
        
        correlation = analysis_results.get('sentiment_roi_correlation', 0)
        if abs(correlation) > 0.3:
            strength = "strong" if abs(correlation) > 0.6 else "moderate"
            direction = "positive" if correlation > 0 else "negative"
            insights.append(f"{strength.title()} {direction} correlation between news sentiment and ROI ({correlation:.3f})")
        
        analysis_results['insights'] = insights
        
        return analysis_results
    
    def _generate_news_integration_recommendation(self, analysis_results: Dict[str, Any]) -> str:
        """Generate recommendation for news integration based on analysis results."""
        correlation = analysis_results.get('sentiment_roi_correlation', 0)
        positive_improvement = analysis_results.get('positive_news_avg_roi', 0) - analysis_results.get('without_news_avg_roi', 0)
        negative_impact = analysis_results.get('without_news_avg_roi', 0) - analysis_results.get('negative_news_avg_roi', 0)
        
        if abs(correlation) > 0.4 and positive_improvement > 1.0:
            return "STRONGLY RECOMMENDED: Integrate news sentiment into trading signals. Strong correlation detected."
        elif abs(correlation) > 0.2 and (positive_improvement > 0.5 or negative_impact > 0.5):
            return "RECOMMENDED: Consider news sentiment integration. Moderate positive impact observed."
        elif analysis_results.get('news_coverage', 0) < 20:
            return "INSUFFICIENT DATA: Need more news coverage to make reliable recommendations."
        else:
            return "NOT RECOMMENDED: News sentiment shows minimal impact on trading performance."
    
    def get_performance_breakdown_by_stock(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[StockPerformanceBreakdown]:
        """Get performance breakdown by individual stock."""
        if start_date is None:
            start_date = (timezone.now() - timedelta(days=30)).date()
        if end_date is None:
            end_date = timezone.now().date()
        
        breakdowns = []
        
        # Get all stocks with signals in the period
        stocks_with_signals = TradingSignal.objects.filter(
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system'
        ).values_list('stock__symbol', flat=True).distinct()
        
        for symbol in stocks_with_signals:
            performance = self.calculate_signal_performance(
                start_date=start_date,
                end_date=end_date,
                stock_symbol=symbol
            )
            
            breakdown = StockPerformanceBreakdown(
                symbol=symbol,
                total_signals=performance.total_signals,
                win_rate=performance.win_rate,
                avg_return=performance.avg_return,
                total_return=performance.total_return,
                best_return=performance.best_signal_return,
                worst_return=performance.worst_signal_return
            )
            breakdowns.append(breakdown)
        
        # Sort by total return descending
        breakdowns.sort(key=lambda x: x.total_return, reverse=True)
        return breakdowns
    
    def calculate_roi_per_signal(self, signal: TradingSignal) -> Optional[float]:
        """
        Calculate ROI for a specific signal.
        
        Args:
            signal: TradingSignal instance
            
        Returns:
            ROI percentage or None if not calculable
        """
        if signal.actual_outcome not in ['profitable', 'loss'] or not signal.outcome_price:
            return None
        
        entry_price = signal.price_at_signal
        exit_price = signal.outcome_price
        
        if signal.signal_type == 'buy':
            roi = ((exit_price - entry_price) / entry_price) * 100
        elif signal.signal_type == 'sell':
            roi = ((entry_price - exit_price) / entry_price) * 100
        else:
            return None
        
        return float(roi)
    
    def update_signal_outcomes(self) -> Dict[str, int]:
        """
        Update outcomes for pending signals based on current market data.
        
        Returns:
            Dictionary with update statistics
        """
        updated_count = 0
        error_count = 0
        
        # Get pending signals older than 1 day
        cutoff_date = timezone.now() - timedelta(days=1)
        pending_signals = TradingSignal.objects.filter(
            actual_outcome='pending',
            created_at__lt=cutoff_date
        ).select_related('stock', 'trading_session')
        
        for signal in pending_signals:
            try:
                outcome = self._determine_signal_outcome(signal)
                if outcome:
                    signal.update_outcome(
                        outcome['result'], 
                        outcome['price'], 
                        outcome['date']
                    )
                    updated_count += 1
                    self.logger.info(f"Updated signal outcome for {signal.stock.symbol}: {outcome['result']}")
                    
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error updating signal {signal.pk}: {str(e)}")
        
        return {
            'updated': updated_count,
            'errors': error_count,
            'processed': pending_signals.count()
        }
    
    def _calculate_signal_returns(self, signals: QuerySet) -> Dict[str, Any]:
        """Calculate return metrics for a set of signals."""
        returns = []
        
        for signal in signals:
            roi = self.calculate_roi_per_signal(signal)
            if roi is not None:
                returns.append(roi)
        
        if not returns:
            return {
                'avg_return': 0.0,
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'best_return': 0.0,
                'worst_return': 0.0
            }
        
        avg_return = sum(returns) / len(returns)
        total_return = sum(returns)
        best_return = max(returns)
        worst_return = min(returns)
        
        # Calculate Sharpe ratio (simplified)
        if len(returns) > 1:
            return_std = (sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
            sharpe_ratio = avg_return / return_std if return_std > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(returns)
        
        return {
            'avg_return': avg_return,
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'best_return': best_return,
            'worst_return': worst_return
        }
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from returns series."""
        if not returns:
            return 0.0
        
        cumulative_returns = []
        cumulative = 0.0
        
        for ret in returns:
            cumulative += ret
            cumulative_returns.append(cumulative)
        
        peak = cumulative_returns[0]
        max_drawdown = 0.0
        
        for value in cumulative_returns[1:]:
            if value > peak:
                peak = value
            else:
                drawdown = peak - value
                max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    def _determine_signal_outcome(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        """
        Determine the outcome of a signal based on subsequent price data.
        
        Args:
            signal: TradingSignal to evaluate
            
        Returns:
            Dictionary with outcome details or None if not determinable
        """
        try:
            # Get price data after signal date
            end_date = signal.trading_session.date + timedelta(days=5)  # 5-day window
            
            subsequent_data = StockData.objects.filter(
                stock=signal.stock,
                trading_session__date__gt=signal.trading_session.date,
                trading_session__date__lte=end_date
            ).order_by('trading_session__date')
            
            if not subsequent_data.exists():
                return None
            
            entry_price = signal.price_at_signal
            target_price = signal.target_price
            stop_loss_price = signal.stop_loss_price
            
            # Check each day for target/stop hit
            for data_point in subsequent_data:
                high_price = data_point.high_price
                low_price = data_point.low_price
                close_price = data_point.close_price
                
                if signal.signal_type == 'buy':
                    # Check if target or stop loss was hit
                    if target_price and high_price and high_price >= target_price:
                        return {
                            'result': 'profitable',
                            'price': target_price,
                            'date': data_point.trading_session.date
                        }
                    elif stop_loss_price and low_price and low_price <= stop_loss_price:
                        return {
                            'result': 'loss',
                            'price': stop_loss_price,
                            'date': data_point.trading_session.date
                        }
                
                elif signal.signal_type == 'sell':
                    # Check if target or stop loss was hit (inverse logic for sell)
                    if target_price and low_price and low_price <= target_price:
                        return {
                            'result': 'profitable',
                            'price': target_price,
                            'date': data_point.trading_session.date
                        }
                    elif stop_loss_price and high_price and high_price >= stop_loss_price:
                        return {
                            'result': 'loss',
                            'price': stop_loss_price,
                            'date': data_point.trading_session.date
                        }
            
            # If no target/stop hit, use final close price
            final_data = subsequent_data.last()
            if final_data and final_data.close_price:
                final_price = final_data.close_price
                
                if signal.signal_type == 'buy':
                    result = 'profitable' if final_price > entry_price else 'loss'
                elif signal.signal_type == 'sell':
                    result = 'profitable' if final_price < entry_price else 'loss'
                else:
                    result = 'break_even'
                
                return {
                    'result': result,
                    'price': final_price,
                    'date': final_data.trading_session.date
                }
            
        except Exception as e:
            self.logger.error(f"Error determining outcome for signal {signal.pk}: {str(e)}")
            return None


class BacktestingFramework:
    """
    Backtesting framework for trading strategy validation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        initial_capital: Decimal = Decimal('10000'),
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run comprehensive backtest of trading signals.
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Starting capital amount
            symbols: List of symbols to test (optional)
            
        Returns:
            Comprehensive backtest results
        """
        self.logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        # Get all signals in the period
        signals = TradingSignal.objects.filter(
            trading_session__date__range=[start_date, end_date],
            generated_by='daily_trading_system'
        ).select_related('stock', 'trading_session').order_by('trading_session__date')
        
        if symbols:
            signals = signals.filter(stock__symbol__in=symbols)
        
        # Simulate trading
        capital = initial_capital
        positions = {}
        trades = []
        daily_returns = []
        
        for signal in signals:
            trade_result = self._simulate_trade(signal, capital, positions)
            if trade_result:
                trades.append(trade_result)
                capital = trade_result['capital_after']
        
        # Calculate performance metrics
        total_return = float((capital - initial_capital) / initial_capital * 100)
        winning_trades = len([t for t in trades if t['profit_loss'] > 0])
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_trade_return = sum(t['return_pct'] for t in trades) / total_trades if total_trades > 0 else 0
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': float(initial_capital),
            'final_capital': float(capital),
            'total_return': total_return,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'avg_trade_return': avg_trade_return,
            'trades': trades,
            'daily_returns': daily_returns
        }
    
    def _simulate_trade(
        self,
        signal: TradingSignal,
        available_capital: Decimal,
        positions: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Simulate execution of a single trade."""
        try:
            # Position sizing based on signal confidence
            position_size = min(available_capital * Decimal('0.1'), available_capital * signal.confidence / 100)
            
            if position_size < Decimal('100'):  # Minimum position size
                return None
            
            # Calculate trade outcome
            roi = SignalPerformanceAnalyzer().calculate_roi_per_signal(signal)
            if roi is None:
                return None
            
            profit_loss = position_size * Decimal(str(roi)) / 100
            capital_after = available_capital + profit_loss
            
            return {
                'signal_id': signal.pk,
                'stock_symbol': signal.stock.symbol,
                'signal_type': signal.signal_type,
                'confidence': float(signal.confidence),
                'position_size': float(position_size),
                'entry_price': float(signal.price_at_signal),
                'exit_price': float(signal.outcome_price) if signal.outcome_price else None,
                'profit_loss': float(profit_loss),
                'return_pct': roi,
                'capital_before': float(available_capital),
                'capital_after': float(capital_after),
                'trade_date': signal.trading_session.date.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error simulating trade for signal {signal.pk}: {str(e)}")
            return None
