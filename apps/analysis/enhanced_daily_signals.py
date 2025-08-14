"""
Enhanced Daily Trading Signal Generator with Time-Weighted News Analysis
======================================================================

This module extends the base DailyTradingSignalGenerator to include 
time-weighted news sentiment analysis for improved intraday trading decisions.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import logging

from django.utils import timezone
from django.db import transaction

from apps.core.models import StockSymbol, TradingSession
from apps.analysis.models import TradingSignal, TechnicalIndicator
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator
from apps.analysis.time_weighted_news import NewsTimeWeightAnalyzer

logger = logging.getLogger(__name__)


class EnhancedDailyTradingSignalGenerator(DailyTradingSignalGenerator):
    """
    Enhanced trading signal generator that includes time-weighted news sentiment analysis
    """
    
    def __init__(self, config_name: str = "intraday_default"):
        super().__init__()
        self.news_analyzer = NewsTimeWeightAnalyzer(config_name)
        self.config_name = config_name
        
        # News impact weights for different signal strengths
        self.news_impact_weights = {
            'STRONG_BUY': 0.2,    # 20% impact on STRONG_BUY signals
            'BUY': 0.15,          # 15% impact on BUY signals  
            'HOLD': 0.1,          # 10% impact on HOLD signals
            'SELL': 0.15,         # 15% impact on SELL signals
            'STRONG_SELL': 0.2,   # 20% impact on STRONG_SELL signals
        }
        
        # Minimum news confidence for signal modification
        self.min_news_confidence = 0.3
    
    def generate_enhanced_signals_for_stock(
        self, 
        stock: StockSymbol, 
        trading_session: Optional[TradingSession] = None,
        include_news_analysis: bool = True
    ) -> Dict[str, Any]:
        """
        Generate trading signals with enhanced news analysis
        
        Args:
            stock: Stock to analyze
            trading_session: Trading session (defaults to current)
            include_news_analysis: Whether to include news sentiment
            
        Returns:
            Dict containing enhanced signal results
        """
        # Get base technical signals first
        base_result = super().generate_signals_for_stock(stock, trading_session)
        
        if not include_news_analysis or base_result['signal'] == 'HOLD':
            return base_result
        
        if trading_session is None:
            trading_session = self._get_current_trading_session()
        
        # Get time-weighted news analysis
        current_time = timezone.now()
        news_data = self.news_analyzer.get_intraday_sentiment_signal(
            stock, current_time
        )
        
        # Enhance the signal with news sentiment
        enhanced_result = self._enhance_signal_with_news(
            base_result, news_data, stock
        )
        
        logger.debug(
            f"{stock.symbol}: {base_result['signal']} → "
            f"{enhanced_result['signal']} (news confidence: "
            f"{news_data['sentiment_data']['confidence']:.2f})"
        )
        
        return enhanced_result
    
    def _enhance_signal_with_news(
        self, 
        base_result: Dict[str, Any], 
        news_data: Dict, 
        stock: StockSymbol
    ) -> Dict[str, Any]:
        """
        Enhance a trading signal with news sentiment analysis
        
        Args:
            base_result: Original technical signal result
            news_data: News sentiment analysis results
            stock: Stock symbol
            
        Returns:
            Enhanced signal result
        """
        sentiment_data = news_data['sentiment_data']
        news_signal = news_data['signal']
        
        # Start with base signal values
        enhanced_result = base_result.copy()
        enhanced_signal = base_result['signal']
        enhanced_confidence = float(base_result['confidence'])
        
        # Collect enhancement reasons
        news_reasons = []
        
        # Only modify signal if news confidence is sufficient
        if sentiment_data['confidence'] < self.min_news_confidence:
            news_reasons.append(f"News confidence too low ({sentiment_data['confidence']:.2f})")
            enhanced_result['news_analysis'] = {
                'applied': False,
                'reason': 'Insufficient news confidence',
                'sentiment_data': sentiment_data
            }
            return enhanced_result
        
        # Get impact weight for this signal type
        signal_type_key = enhanced_signal.replace('_', '')
        if signal_type_key not in self.news_impact_weights:
            signal_type_key = 'HOLD'
        impact_weight = self.news_impact_weights.get(signal_type_key, 0.1)
        
        # Calculate news impact on confidence
        news_sentiment = sentiment_data['weighted_sentiment_score']
        news_momentum = sentiment_data['sentiment_momentum']
        
        # Apply news sentiment modifications
        if news_signal in ['STRONG_BUY', 'BUY']:
            if enhanced_signal in ['sell']:
                # Positive news conflicts with sell signal
                if news_sentiment > 0.3:
                    enhanced_signal = 'hold'
                    enhanced_confidence *= 0.7  # Reduce confidence
                    news_reasons.append(f"Positive news ({news_sentiment:.2f}) conflicts with sell signal")
                else:
                    # Moderate positive news, reduce confidence slightly
                    enhanced_confidence *= (1.0 - impact_weight * news_sentiment)
                    news_reasons.append(f"Moderate positive news reduces sell confidence")
                    
            elif enhanced_signal in ['buy']:
                # Positive news reinforces buy signal
                confidence_boost = impact_weight * news_sentiment * sentiment_data['confidence']
                enhanced_confidence = min(100.0, enhanced_confidence + confidence_boost * 100)
                news_reasons.append(
                    f"Positive news reinforces buy signal (+{confidence_boost:.2f})"
                )
                
            elif enhanced_signal == 'hold':
                # Positive news may upgrade HOLD to BUY
                if news_sentiment > 0.3 and sentiment_data['confidence'] > 0.6:
                    enhanced_signal = 'buy'
                    enhanced_confidence = 60 + (news_sentiment * sentiment_data['confidence'] * 30)
                    news_reasons.append(f"Strong positive news upgrades HOLD to BUY")
                else:
                    news_reasons.append(f"Positive news noted but insufficient for upgrade")
        
        elif news_signal in ['STRONG_SELL', 'SELL']:
            if enhanced_signal in ['buy']:
                # Negative news conflicts with buy signal
                if news_sentiment < -0.3:
                    enhanced_signal = 'hold'
                    enhanced_confidence *= 0.7  # Reduce confidence
                    news_reasons.append(f"Negative news ({news_sentiment:.2f}) conflicts with buy signal")
                else:
                    # Moderate negative news, reduce confidence slightly
                    enhanced_confidence *= (1.0 - impact_weight * abs(news_sentiment))
                    news_reasons.append(f"Moderate negative news reduces buy confidence")
                    
            elif enhanced_signal in ['sell']:
                # Negative news reinforces sell signal
                confidence_boost = impact_weight * abs(news_sentiment) * sentiment_data['confidence']
                enhanced_confidence = min(100.0, enhanced_confidence + confidence_boost * 100)
                news_reasons.append(
                    f"Negative news reinforces sell signal (+{confidence_boost:.2f})"
                )
                
            elif enhanced_signal == 'hold':
                # Negative news may downgrade HOLD to SELL
                if news_sentiment < -0.3 and sentiment_data['confidence'] > 0.6:
                    enhanced_signal = 'sell'
                    enhanced_confidence = 60 + (abs(news_sentiment) * sentiment_data['confidence'] * 30)
                    news_reasons.append(f"Strong negative news downgrades HOLD to SELL")
                else:
                    news_reasons.append(f"Negative news noted but insufficient for downgrade")
        
        # Apply momentum adjustments
        if abs(news_momentum) > 0.2:
            momentum_impact = impact_weight * 0.5 * news_momentum * sentiment_data['confidence']
            enhanced_confidence = max(0.0, min(100.0, enhanced_confidence + momentum_impact * 100))
            news_reasons.append(f"News momentum adjustment: {momentum_impact:+.2f}")
        
        # Add recent news impact
        if sentiment_data['recent_news_count'] > 0:
            recency_boost = min(10.0, sentiment_data['recent_news_count'] * 2)
            enhanced_confidence = min(100.0, enhanced_confidence + recency_boost)
            news_reasons.append(f"Recent news activity boost (+{recency_boost:.2f})")
        
        # Add breaking news impact
        if sentiment_data['breaking_news_impact'] > 0.5:
            breaking_impact = min(15.0, sentiment_data['breaking_news_impact'] * 20)
            enhanced_confidence = min(100.0, enhanced_confidence + breaking_impact)
            news_reasons.append(f"Breaking news impact (+{breaking_impact:.2f})")
        
        # Update enhanced result
        enhanced_result.update({
            'signal': enhanced_signal,
            'confidence': enhanced_confidence,
            'news_analysis': {
                'applied': True,
                'original_signal': base_result['signal'],
                'original_confidence': base_result['confidence'],
                'news_signal': news_signal,
                'sentiment_score': news_sentiment,
                'sentiment_momentum': news_momentum,
                'news_confidence': sentiment_data['confidence'],
                'reasons': news_reasons,
                'sentiment_data': sentiment_data
            }
        })
        
        # Update the reason field to include news analysis
        original_reason = enhanced_result.get('reason', '')
        if news_reasons:
            enhanced_result['reason'] = f"{original_reason}. News: {'; '.join(news_reasons)}"
        
        return enhanced_result


def generate_enhanced_daily_signals_for_stocks(
    stocks: List[str],
    config_name: str = "intraday_default"
) -> Dict[str, Any]:
    """
    Generate enhanced daily trading signals for multiple stocks
    
    Args:
        stocks: List of stock symbols to analyze
        session_date: Date to analyze (defaults to today)
        config_name: Time weight configuration to use
        
    Returns:
        Dict containing enhanced signal results for all stocks
    """
    if session_date is None:
        session_date = timezone.now().date()
    
    # Get or create trading session
    session, created = TradingSession.objects.get_or_create(
        date=session_date,
        defaults={'status': 'open'}
    )
    
    # Filter stocks
    stock_objects = StockSymbol.objects.filter(
        symbol__in=stocks, 
        is_active=True
    )
    
    # Generate enhanced signals
    generator = EnhancedDailyTradingSignalGenerator(config_name)
    results = {
        'session_date': session_date,
        'config_used': config_name,
        'analysis_time': timezone.now(),
        'signals': {},
        'summary': {
            'total_stocks': len(stocks),
            'analyzed_stocks': 0,
            'signals_enhanced': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0,
        }
    }
    
    for stock in stock_objects:
        try:
            signal_result = generator.generate_enhanced_signals_for_stock(
                stock, session
            )
            results['signals'][stock.symbol] = signal_result
            results['summary']['analyzed_stocks'] += 1
            
            # Count signals
            signal_type = signal_result['signal']
            if signal_type == 'buy':
                results['summary']['buy_signals'] += 1
            elif signal_type == 'sell':
                results['summary']['sell_signals'] += 1
            else:
                results['summary']['hold_signals'] += 1
            
            # Count enhanced signals
            if signal_result.get('news_analysis', {}).get('applied', False):
                results['summary']['signals_enhanced'] += 1
                
        except Exception as e:
            logger.error(f"Error analyzing {stock.symbol}: {e}")
            results['signals'][stock.symbol] = {
                'error': str(e),
                'signal': 'HOLD',
                'confidence': 0
            }
    
    logger.info(
        f"Generated enhanced signals for {results['summary']['analyzed_stocks']} stocks, "
        f"{results['summary']['signals_enhanced']} enhanced with news analysis"
    )
    
    return results

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

from django.utils import timezone
from django.db import transaction

from apps.core.models import StockSymbol, TradingSession
from apps.analysis.models import TradingSignal, TechnicalIndicator
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator
from apps.analysis.time_weighted_news import NewsTimeWeightAnalyzer

logger = logging.getLogger(__name__)


class EnhancedDailyTradingSignalGenerator(DailyTradingSignalGenerator):
    """
    Enhanced trading signal generator that includes time-weighted news sentiment analysis
    """
    
    def __init__(self, config_name: str = "intraday_default"):
        super().__init__()
        self.news_analyzer = NewsTimeWeightAnalyzer(config_name)
        self.config_name = config_name
        
        # News impact weights for different signal strengths
        self.news_impact_weights = {
            'STRONG_BUY': 0.2,    # 20% impact on STRONG_BUY signals
            'BUY': 0.15,          # 15% impact on BUY signals  
            'HOLD': 0.1,          # 10% impact on HOLD signals
            'SELL': 0.15,         # 15% impact on SELL signals
            'STRONG_SELL': 0.2,   # 20% impact on STRONG_SELL signals
        }
        
        # Minimum news confidence for signal modification
        self.min_news_confidence = 0.3
    
    def generate_signals_for_session(
        self, 
        session: TradingSession, 
        stocks: Optional[List[StockSymbol]] = None,
        include_news_analysis: bool = True
    ) -> Dict[str, any]:
        """
        Generate trading signals with enhanced news analysis
        
        Args:
            session: Trading session to analyze
            stocks: Specific stocks to analyze (None for all)
            include_news_analysis: Whether to include news sentiment
            
        Returns:
            Dict containing enhanced signal results
        """
        # Get base technical signals first
        base_results = super().generate_signals_for_session(session, stocks)
        
        if not include_news_analysis:
            return base_results
        
        # Enhance signals with news analysis
        enhanced_signals = []
        news_impacts = {}
        
        logger.info(f"Enhancing {len(base_results['signals'])} signals with news analysis...")
        
        for base_signal in base_results['signals']:
            stock = base_signal.stock
            
            # Get time-weighted news analysis
            news_data = self.news_analyzer.get_intraday_sentiment_signal(
                stock, session.date
            )
            
            # Enhance the signal with news sentiment
            enhanced_signal = self._enhance_signal_with_news(
                base_signal, news_data, session
            )
            
            enhanced_signals.append(enhanced_signal)
            news_impacts[stock.symbol] = news_data
            
            logger.debug(
                f"{stock.symbol}: {base_signal.signal_type} → "
                f"{enhanced_signal.signal_type} (news confidence: "
                f"{news_data['sentiment_data']['confidence']:.2f})"
            )
        
        # Calculate enhancement statistics
        enhancement_stats = self._calculate_enhancement_stats(
            base_results['signals'], enhanced_signals
        )
        
        return {
            'signals': enhanced_signals,
            'session': session,
            'analysis_time': timezone.now(),
            'base_signal_count': len(base_results['signals']),
            'enhanced_signal_count': len(enhanced_signals),
            'news_impacts': news_impacts,
            'enhancement_stats': enhancement_stats,
            'config_used': self.config_name,
        }
    
    def _enhance_signal_with_news(
        self, 
        base_signal: TradingSignal, 
        news_data: Dict, 
        session: TradingSession
    ) -> TradingSignal:
        """
        Enhance a single trading signal with news sentiment analysis
        
        Args:
            base_signal: Original technical signal
            news_data: News sentiment analysis results
            session: Trading session
            
        Returns:
            Enhanced trading signal
        """
        sentiment_data = news_data['sentiment_data']
        news_signal = news_data['signal']
        
        # Start with base signal values
        enhanced_type = base_signal.signal_type
        enhanced_confidence = float(base_signal.confidence)
        enhanced_reasons = base_signal.reasoning.copy() if base_signal.reasoning else []
        
        # Only modify signal if news confidence is sufficient
        if sentiment_data['confidence'] < self.min_news_confidence:
            enhanced_reasons.append(f"News confidence too low ({sentiment_data['confidence']:.2f})")
            return self._create_enhanced_signal(
                base_signal, enhanced_type, enhanced_confidence, enhanced_reasons, session
            )
        
        # Get impact weight for this signal type
        impact_weight = self.news_impact_weights.get(enhanced_type, 0.1)
        
        # Calculate news impact on confidence
        news_sentiment = sentiment_data['weighted_sentiment_score']
        news_momentum = sentiment_data['sentiment_momentum']
        
        # Apply news sentiment modifications
        if news_signal in ['STRONG_BUY', 'BUY']:
            if enhanced_type in ['SELL', 'STRONG_SELL']:
                # Positive news conflicts with sell signal
                if news_sentiment > 0.3:
                    enhanced_type = 'HOLD'
                    enhanced_confidence *= 0.7  # Reduce confidence
                    enhanced_reasons.append(f"Positive news ({news_sentiment:.2f}) conflicts with sell signal")
                else:
                    # Moderate positive news, reduce confidence slightly
                    enhanced_confidence *= (1.0 - impact_weight * news_sentiment)
                    enhanced_reasons.append(f"Moderate positive news reduces sell confidence")
                    
            elif enhanced_type in ['BUY', 'STRONG_BUY']:
                # Positive news reinforces buy signal
                confidence_boost = impact_weight * news_sentiment * sentiment_data['confidence']
                enhanced_confidence = min(1.0, enhanced_confidence + confidence_boost)
                
                if news_sentiment > 0.4 and enhanced_type == 'BUY':
                    enhanced_type = 'STRONG_BUY'
                
                enhanced_reasons.append(
                    f"Positive news reinforces buy signal (+{confidence_boost:.2f})"
                )
                
            elif enhanced_type == 'HOLD':
                # Positive news may upgrade HOLD to BUY
                if news_sentiment > 0.3 and sentiment_data['confidence'] > 0.6:
                    enhanced_type = 'BUY'
                    enhanced_confidence = 0.6 + (news_sentiment * sentiment_data['confidence'] * 0.3)
                    enhanced_reasons.append(f"Strong positive news upgrades HOLD to BUY")
                else:
                    enhanced_reasons.append(f"Positive news noted but insufficient for upgrade")
        
        elif news_signal in ['STRONG_SELL', 'SELL']:
            if enhanced_type in ['BUY', 'STRONG_BUY']:
                # Negative news conflicts with buy signal
                if news_sentiment < -0.3:
                    enhanced_type = 'HOLD'
                    enhanced_confidence *= 0.7  # Reduce confidence
                    enhanced_reasons.append(f"Negative news ({news_sentiment:.2f}) conflicts with buy signal")
                else:
                    # Moderate negative news, reduce confidence slightly
                    enhanced_confidence *= (1.0 - impact_weight * abs(news_sentiment))
                    enhanced_reasons.append(f"Moderate negative news reduces buy confidence")
                    
            elif enhanced_type in ['SELL', 'STRONG_SELL']:
                # Negative news reinforces sell signal
                confidence_boost = impact_weight * abs(news_sentiment) * sentiment_data['confidence']
                enhanced_confidence = min(1.0, enhanced_confidence + confidence_boost)
                
                if news_sentiment < -0.4 and enhanced_type == 'SELL':
                    enhanced_type = 'STRONG_SELL'
                
                enhanced_reasons.append(
                    f"Negative news reinforces sell signal (+{confidence_boost:.2f})"
                )
                
            elif enhanced_type == 'HOLD':
                # Negative news may downgrade HOLD to SELL
                if news_sentiment < -0.3 and sentiment_data['confidence'] > 0.6:
                    enhanced_type = 'SELL'
                    enhanced_confidence = 0.6 + (abs(news_sentiment) * sentiment_data['confidence'] * 0.3)
                    enhanced_reasons.append(f"Strong negative news downgrades HOLD to SELL")
                else:
                    enhanced_reasons.append(f"Negative news noted but insufficient for downgrade")
        
        # Apply momentum adjustments
        if abs(news_momentum) > 0.2:
            momentum_impact = impact_weight * 0.5 * news_momentum * sentiment_data['confidence']
            enhanced_confidence = max(0.1, min(1.0, enhanced_confidence + momentum_impact))
            enhanced_reasons.append(f"News momentum adjustment: {momentum_impact:+.2f}")
        
        # Add recent news impact
        if sentiment_data['recent_news_count'] > 0:
            recency_boost = min(0.1, sentiment_data['recent_news_count'] * 0.02)
            enhanced_confidence = min(1.0, enhanced_confidence + recency_boost)
            enhanced_reasons.append(f"Recent news activity boost (+{recency_boost:.2f})")
        
        # Add breaking news impact
        if sentiment_data['breaking_news_impact'] > 0.5:
            breaking_impact = min(0.15, sentiment_data['breaking_news_impact'] * 0.2)
            enhanced_confidence = min(1.0, enhanced_confidence + breaking_impact)
            enhanced_reasons.append(f"Breaking news impact (+{breaking_impact:.2f})")
        
        return self._create_enhanced_signal(
            base_signal, enhanced_type, enhanced_confidence, enhanced_reasons, session
        )
    
    def _create_enhanced_signal(
        self,
        base_signal: TradingSignal,
        enhanced_type: str,
        enhanced_confidence: float,
        enhanced_reasons: List[str],
        session: TradingSession
    ) -> TradingSignal:
        """
        Create an enhanced trading signal based on the original signal
        """
        enhanced_signal = TradingSignal.objects.create(
            stock=base_signal.stock,
            session=session,
            signal_type=enhanced_type,
            confidence=Decimal(str(round(enhanced_confidence, 3))),
            entry_price=base_signal.entry_price,
            stop_loss=base_signal.stop_loss,
            take_profit=base_signal.take_profit,
            expected_return=base_signal.expected_return,
            risk_level=base_signal.risk_level,
            position_size=base_signal.position_size,
            reasoning=enhanced_reasons,
            technical_data=base_signal.technical_data,
            is_active=True,
        )
        
        # Copy technical indicators used
        for indicator in base_signal.indicators_used.all():
            enhanced_signal.indicators_used.add(indicator)
        
        return enhanced_signal
    
    def _calculate_enhancement_stats(
        self, 
        base_signals: List[TradingSignal], 
        enhanced_signals: List[TradingSignal]
    ) -> Dict[str, any]:
        """
        Calculate statistics about signal enhancements
        """
        signal_changes = {}
        confidence_changes = []
        
        for base, enhanced in zip(base_signals, enhanced_signals):
            # Track signal type changes
            if base.signal_type != enhanced.signal_type:
                change_key = f"{base.signal_type}→{enhanced.signal_type}"
                signal_changes[change_key] = signal_changes.get(change_key, 0) + 1
            
            # Track confidence changes
            conf_change = float(enhanced.confidence) - float(base.confidence)
            confidence_changes.append(conf_change)
        
        return {
            'signal_type_changes': signal_changes,
            'avg_confidence_change': sum(confidence_changes) / len(confidence_changes) if confidence_changes else 0.0,
            'confidence_improvements': len([c for c in confidence_changes if c > 0]),
            'confidence_reductions': len([c for c in confidence_changes if c < 0]),
            'signals_upgraded': len([change for change in signal_changes.keys() if 'BUY' in change.split('→')[1]]),
            'signals_downgraded': len([change for change in signal_changes.keys() if 'SELL' in change.split('→')[1]]),
        }


def generate_enhanced_daily_signals(
    session_date: datetime = None,
    config_name: str = "intraday_default",
    stocks: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    Convenience function to generate enhanced daily trading signals
    
    Args:
        session_date: Date to analyze (defaults to today)
        config_name: Time weight configuration to use
        stocks: List of stock symbols to analyze (None for all)
        
    Returns:
        Dict containing enhanced signal results
    """
    if session_date is None:
        session_date = timezone.now().date()
    
    # Get or create trading session
    session, created = TradingSession.objects.get_or_create(
        date=session_date,
        defaults={'status': 'open'}
    )
    
    # Filter stocks if specified
    stock_objects = None
    if stocks:
        stock_objects = StockSymbol.objects.filter(symbol__in=stocks, is_active=True)
    
    # Generate enhanced signals
    generator = EnhancedDailyTradingSignalGenerator(config_name)
    results = generator.generate_signals_for_session(session, stock_objects)
    
    logger.info(
        f"Generated {len(results['signals'])} enhanced signals for {session_date} "
        f"using {config_name} configuration"
    )
    
    return results
