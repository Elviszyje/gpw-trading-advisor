"""
Daily Trading Signal Generation Engine for GPW Trading Advisor.

This module generates BUY/SELL/HOLD signals specifically optimized for intraday trading.
All positions must be opened and closed within the same trading session.

Key Features:
- Intraday-optimized technical indicators
- Session-based position management
- Automatic exit before market close
- Risk management for daily trading
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import QuerySet
import logging

from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData
from apps.analysis.models import TechnicalIndicator, IndicatorValue, TradingSignal
from apps.analysis.technical_indicators import TechnicalAnalysisEngine, IndicatorCalculationService
from apps.users.models import User, UserTradingPreferences

logger = logging.getLogger(__name__)


class DailyTradingSignalGenerator:
    """
    Generates trading signals optimized for intraday (daily) trading.
    
    Business Rules:
    - All positions must be closed within the same trading session
    - No overnight positions
    - Entry signals generated during trading hours (9:00-16:50)
    - Automatic exit signals before market close (16:50)
    - Risk management with tight stop-losses (1-3%)
    - Realistic profit targets (2-5% for intraday)
    """
    
    # GPW trading hours (Warsaw time)
    MARKET_OPEN = time(9, 0, 0)    # 09:00
    MARKET_CLOSE = time(16, 50, 0)  # 16:50 (10 minutes before official close)
    LAST_ENTRY_TIME = time(15, 0, 0)  # 15:00 - last entry to allow time for exits
    
    # Daily trading parameters
    INTRADAY_STOP_LOSS_PCT = Decimal('2.0')  # 2% stop loss
    INTRADAY_TAKE_PROFIT_PCT = Decimal('3.0')  # 3% take profit
    MIN_CONFIDENCE_SCORE = Decimal('60.0')  # Minimum 60% confidence for signals
    
    def __init__(self):
        self.indicator_service = IndicatorCalculationService()
        self.analysis_engine = TechnicalAnalysisEngine()
    
    def generate_personalized_signals_for_user(
        self, 
        user: User,
        stock: StockSymbol, 
        trading_session: Optional[TradingSession] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized trading signals based on user preferences.
        
        Args:
            user: User instance with trading preferences
            stock: StockSymbol instance
            trading_session: Specific trading session (default: current session)
            
        Returns:
            Dictionary with personalized signal analysis and recommendations
        """
        # Get user preferences
        preferences = self._get_user_preferences(user)
        
        # Check if stock meets user's criteria
        if not self._should_recommend_stock_to_user(stock, preferences):
            return {
                'stock': stock.symbol,
                'signal': 'HOLD',
                'confidence': 0,
                'reason': 'Stock does not meet user preferences (liquidity, market cap, or sector exclusions)',
                'can_enter': False,
                'timestamp': timezone.now(),
                'user_personalized': True
            }
        
        # Generate base signal using existing logic
        base_result = self.generate_signals_for_stock(stock, trading_session)
        
        # Apply user-specific filters and adjustments
        personalized_result = self._personalize_signal_for_user(base_result, preferences, stock)
        
        return personalized_result
    
    def generate_signals_for_user_portfolio(
        self, 
        user: User,
        trading_session: Optional[TradingSession] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate personalized signals for all stocks suitable for the user.
        
        Args:
            user: User instance with trading preferences
            trading_session: Specific trading session (default: current session)
            
        Returns:
            List of personalized signal dictionaries
        """
        preferences = self._get_user_preferences(user)
        
        # Get stocks that meet user's criteria
        suitable_stocks = self._get_suitable_stocks_for_user(preferences)
        
        signals = []
        signals_generated_today = 0
        
        for stock in suitable_stocks:
            # Respect user's daily signal limit
            if signals_generated_today >= preferences.max_signals_per_day:
                break
                
            signal = self.generate_personalized_signals_for_user(user, stock, trading_session)
            
            # Only include actionable signals in the count
            if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] > 0:
                signals_generated_today += 1
                
            signals.append(signal)
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: float(x.get('confidence', 0)), reverse=True)
        
        return signals
    
    def _get_user_preferences(self, user: User) -> UserTradingPreferences:
        """Get user trading preferences or create defaults."""
        try:
            return getattr(user, 'trading_preferences', None) or UserTradingPreferences.get_default_preferences(user)
        except Exception as e:
            logger.info(f"Creating default trading preferences for user {user.username}: {e}")
            return UserTradingPreferences.get_default_preferences(user)
    
    def _should_recommend_stock_to_user(self, stock: StockSymbol, preferences: UserTradingPreferences) -> bool:
        """Check if stock meets user's criteria for recommendations."""
        try:
            # Get latest stock data
            latest_data = StockData.objects.filter(stock=stock).order_by('-trading_session__date').first()
            
            if not latest_data or not latest_data.close_price:
                return False
            
            # Prepare stock data for preferences check
            stock_data = {
                'current_price': float(latest_data.close_price),
                'avg_daily_volume': self._get_average_daily_volume(stock),
                'market_cap_millions': self._estimate_market_cap(stock, latest_data.close_price),
                'sector': getattr(stock, 'sector', ''),
            }
            
            return preferences.should_recommend_stock(stock_data)
            
        except Exception as e:
            logger.error(f"Error checking stock suitability for user: {e}")
            return False
    
    def _get_suitable_stocks_for_user(self, preferences: UserTradingPreferences) -> QuerySet[StockSymbol]:
        """Get stocks that meet user's basic criteria."""
        # Start with active stocks
        stocks = StockSymbol.objects.filter(is_active=True)
        
        # Apply basic filters based on preferences
        if hasattr(preferences, 'preferred_sectors') and preferences.preferred_sectors.exists():
            # If user has preferred sectors, only include those
            preferred_symbols = preferences.preferred_sectors.all()
            stocks = stocks.filter(pk__in=[s.pk for s in preferred_symbols])
        
        # Filter by market cap and volume (we'll do detailed filtering in _should_recommend_stock_to_user)
        return stocks.order_by('symbol')[:50]  # Limit to 50 stocks for performance
    
    def _personalize_signal_for_user(
        self, 
        base_signal: Dict[str, Any], 
        preferences: UserTradingPreferences,
        stock: StockSymbol
    ) -> Dict[str, Any]:
        """Apply user-specific personalization to the base signal."""
        
        personalized_signal = base_signal.copy()
        personalized_signal['user_personalized'] = True
        
        # Apply user's confidence threshold
        if float(base_signal.get('confidence', 0)) < float(preferences.min_confidence_threshold):
            personalized_signal.update({
                'signal': 'HOLD',
                'confidence': base_signal.get('confidence', 0),
                'reason': f"Confidence {base_signal.get('confidence', 0)}% below user threshold {preferences.min_confidence_threshold}%"
            })
            return personalized_signal
        
        # Calculate personalized risk parameters
        if base_signal['signal'] in ['BUY', 'SELL']:
            personalized_risk = self._calculate_personalized_risk_parameters(
                stock, 
                base_signal, 
                preferences
            )
            personalized_signal['risk_management'] = personalized_risk
            
            # Add position sizing recommendation
            position_size = preferences.get_position_size_for_signal(
                float(base_signal.get('confidence', 0))
            )
            personalized_signal['recommended_position_size_pln'] = position_size
            
            # Add holding time recommendation
            personalized_signal['recommended_holding_time_hours'] = preferences.preferred_holding_time_hours
            personalized_signal['max_holding_time_hours'] = preferences.max_holding_time_hours
        
        return personalized_signal
    
    def _calculate_personalized_risk_parameters(
        self, 
        stock: StockSymbol, 
        signal: Dict[str, Any],
        preferences: UserTradingPreferences
    ) -> Dict[str, Any]:
        """Calculate risk parameters based on user preferences."""
        current_price = self._get_latest_price(stock)
        
        if not current_price or signal['signal'] == 'HOLD':
            return {}
        
        price = float(current_price)
        
        # Use user's personalized percentages instead of hardcoded values
        stop_loss_pct = preferences.get_effective_stop_loss_pct()
        take_profit_pct = preferences.get_effective_take_profit_pct()
        
        if signal['signal'] == 'BUY':
            stop_loss = price * (1 - stop_loss_pct / 100)
            take_profit = price * (1 + take_profit_pct / 100)
        else:  # SELL
            stop_loss = price * (1 + stop_loss_pct / 100)
            take_profit = price * (1 - take_profit_pct / 100)
        
        # Calculate position size based on user's capital and preferences
        position_size_pln = preferences.get_position_size_for_signal(
            float(signal.get('confidence', 0))
        )
        
        if preferences.available_capital:
            position_size_pct = (position_size_pln / float(preferences.available_capital)) * 100
        else:
            position_size_pct = 0
        
        return {
            'entry_price': price,
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'position_size_pln': round(position_size_pln, 2),
            'position_size_pct': round(position_size_pct, 1),
            'risk_reward_ratio': abs(take_profit - price) / abs(price - stop_loss) if abs(price - stop_loss) > 0 else 0,
            'max_loss_pct': stop_loss_pct,
            'target_profit_pct': take_profit_pct,
            'max_loss_amount_pln': round(position_size_pln * (stop_loss_pct / 100), 2),
            'target_profit_amount_pln': round(position_size_pln * (take_profit_pct / 100), 2),
            'trading_style': preferences.trading_style,
        }
    
    def _get_average_daily_volume(self, stock: StockSymbol, days: int = 30) -> int:
        """Calculate average daily volume for the stock."""
        recent_data = StockData.objects.filter(
            stock=stock
        ).order_by('-trading_session__date')[:days]
        
        if not recent_data:
            return 0
        
        total_volume = sum(data.volume for data in recent_data if data.volume)
        return total_volume // len(recent_data) if recent_data else 0
    
    def _estimate_market_cap(self, stock: StockSymbol, current_price: Decimal) -> float:
        """Estimate market cap in millions PLN (simplified)."""
        # This is a simplified estimation - in real implementation you'd need actual share count
        # For now, we'll use a rough estimate based on stock type and price
        
        # Rough estimate for different stock categories
        if current_price > 100:
            return float(current_price) * 10  # Large companies
        elif current_price > 10:
            return float(current_price) * 5   # Medium companies
        else:
            return float(current_price) * 2   # Smaller companies
    
    def generate_signals_for_stock(
        self, 
        stock: StockSymbol, 
        trading_session: Optional[TradingSession] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Generate daily trading signals for a specific stock.
        
        Args:
            stock: StockSymbol instance
            trading_session: Specific trading session (default: current session)
            user: Optional user for personalized signals
            
        Returns:
            Dictionary with signal analysis and recommendations
        """
        if trading_session is None:
            trading_session = self._get_current_trading_session()
        
        logger.info(f"Generating daily trading signals for {stock.symbol}")
        
        # Check if market is open for new entries
        current_time = timezone.localtime().time()
        can_enter_positions = self._can_enter_new_positions(current_time)
        
        # Get latest indicator values
        indicators = self._get_latest_indicators(stock, trading_session)
        
        if not indicators:
            logger.warning(f"No indicator data available for {stock.symbol}")
            return {
                'stock': stock.symbol,
                'signal': 'HOLD',
                'confidence': 0,
                'reason': 'Insufficient technical data',
                'can_enter': can_enter_positions,
                'timestamp': timezone.now()
            }
        
        # Analyze current market conditions
        market_analysis = self._analyze_market_conditions(indicators, current_time)
        
        # Generate signal based on multiple indicators
        signal_result = self._generate_composite_signal(indicators, market_analysis)
        
        # Apply daily trading filters (with user-specific thresholds if provided)
        filtered_signal = self._apply_daily_trading_filters(
            signal_result, 
            current_time, 
            can_enter_positions,
            user
        )
        
        # Calculate position sizing and risk management (with user preferences if provided)
        risk_params = self._calculate_risk_parameters(stock, filtered_signal, user)
        
        result = {
            'stock': stock.symbol,
            'signal': filtered_signal['action'],
            'confidence': filtered_signal['confidence'],
            'reason': filtered_signal['reason'],
            'can_enter': can_enter_positions,
            'timestamp': timezone.now(),
            'indicators': {
                'rsi': indicators.get('rsi'),
                'macd': indicators.get('macd'),
                'bollinger': indicators.get('bollinger'),
                'price_trend': market_analysis['trend']
            },
            'risk_management': risk_params,
            'market_timing': {
                'time_to_close': self._time_until_market_close(current_time),
                'trading_session': trading_session.date.isoformat()
            }
        }
        
        # Save signal to database if it's actionable
        if filtered_signal['action'] in ['BUY', 'SELL']:
            self._save_trading_signal(stock, trading_session, result)
        
        return result
    
    def _can_enter_new_positions(self, current_time: time) -> bool:
        """Check if new positions can be entered based on current time."""
        return (
            current_time >= self.MARKET_OPEN and 
            current_time <= self.LAST_ENTRY_TIME
        )
    
    def _get_current_trading_session(self) -> TradingSession:
        """Get or create current trading session."""
        today = timezone.localtime().date()
        session, created = TradingSession.objects.get_or_create(
            date=today,
            defaults={'is_active': True}
        )
        return session
    
    def _get_latest_indicators(
        self, 
        stock: StockSymbol, 
        trading_session: TradingSession
    ) -> Dict[str, Dict[str, Any]]:
        """Retrieve latest indicator values for the stock."""
        indicators = {}
        
        # Get RSI
        rsi_indicator = TechnicalIndicator.objects.filter(indicator_type='rsi').first()
        if rsi_indicator:
            rsi_value = IndicatorValue.objects.filter(
                stock=stock,
                indicator=rsi_indicator,
                trading_session=trading_session
            ).first()
            
            if rsi_value and rsi_value.value:
                indicators['rsi'] = {
                    'value': float(rsi_value.value),
                    'overbought': float(rsi_value.value) >= 70,
                    'oversold': float(rsi_value.value) <= 30,
                    'signal': self._interpret_rsi_for_intraday(float(rsi_value.value))
                }
        
        # Get MACD
        macd_indicator = TechnicalIndicator.objects.filter(indicator_type='macd').first()
        if macd_indicator:
            macd_value = IndicatorValue.objects.filter(
                stock=stock,
                indicator=macd_indicator,
                trading_session=trading_session
            ).first()
            
            if macd_value and macd_value.value and macd_value.value_signal:
                macd_line = float(macd_value.value)
                signal_line = float(macd_value.value_signal)
                histogram = macd_line - signal_line
                
                indicators['macd'] = {
                    'macd_line': macd_line,
                    'signal_line': signal_line,
                    'histogram': histogram,
                    'bullish': histogram > 0,
                    'signal': self._interpret_macd_for_intraday(histogram)
                }
        
        # Get Bollinger Bands
        bb_indicator = TechnicalIndicator.objects.filter(indicator_type='bollinger').first()
        if bb_indicator:
            bb_value = IndicatorValue.objects.filter(
                stock=stock,
                indicator=bb_indicator,
                trading_session=trading_session
            ).first()
            
            if bb_value and all([bb_value.value, bb_value.value_upper, bb_value.value_lower]):
                # Get current price
                latest_price = self._get_latest_price(stock)
                if latest_price:
                    upper = float(bb_value.value_upper or 0)
                    middle = float(bb_value.value or 0)
                    lower = float(bb_value.value_lower or 0)
                    price = float(latest_price)
                    
                    indicators['bollinger'] = {
                        'upper': upper,
                        'middle': middle,
                        'lower': lower,
                        'current_price': price,
                        'position': self._get_bb_position(price, upper, middle, lower),
                        'signal': self._interpret_bollinger_for_intraday(price, upper, middle, lower)
                    }
        
        return indicators
    
    def _interpret_rsi_for_intraday(self, rsi_value: float) -> str:
        """Interpret RSI for intraday trading with more aggressive thresholds."""
        if rsi_value >= 75:  # More aggressive for intraday
            return 'STRONG_SELL'
        elif rsi_value >= 65:
            return 'SELL'
        elif rsi_value <= 25:  # More aggressive for intraday
            return 'STRONG_BUY'
        elif rsi_value <= 35:
            return 'BUY'
        else:
            return 'NEUTRAL'
    
    def _interpret_macd_for_intraday(self, histogram: float) -> str:
        """Interpret MACD for intraday trading."""
        if histogram > 0.1:  # Strong bullish divergence
            return 'STRONG_BUY'
        elif histogram > 0:
            return 'BUY'
        elif histogram < -0.1:  # Strong bearish divergence
            return 'STRONG_SELL'
        elif histogram < 0:
            return 'SELL'
        else:
            return 'NEUTRAL'
    
    def _get_bb_position(self, price: float, upper: float, middle: float, lower: float) -> str:
        """Determine price position relative to Bollinger Bands."""
        if price >= upper:
            return 'ABOVE_UPPER'
        elif price >= middle:
            return 'UPPER_HALF'
        elif price >= lower:
            return 'LOWER_HALF'
        else:
            return 'BELOW_LOWER'
    
    def _interpret_bollinger_for_intraday(
        self, 
        price: float, 
        upper: float, 
        middle: float, 
        lower: float
    ) -> str:
        """Interpret Bollinger Bands for intraday trading."""
        if price <= lower:  # Price at/below lower band
            return 'STRONG_BUY'  # Oversold condition
        elif price >= upper:  # Price at/above upper band
            return 'STRONG_SELL'  # Overbought condition
        elif price > middle:
            return 'WEAK_SELL'  # Above middle, potential resistance
        elif price < middle:
            return 'WEAK_BUY'  # Below middle, potential support
        else:
            return 'NEUTRAL'
    
    def _get_latest_price(self, stock: StockSymbol) -> Optional[Decimal]:
        """Get the most recent price for the stock."""
        latest_data = StockData.objects.filter(
            stock=stock,
            is_active=True
        ).order_by('-data_timestamp').first()
        
        return latest_data.close_price if latest_data else None
    
    def _analyze_market_conditions(
        self, 
        indicators: Dict[str, Dict[str, Any]], 
        current_time: time
    ) -> Dict[str, Any]:
        """Analyze overall market conditions for the stock."""
        bullish_signals = 0
        bearish_signals = 0
        signal_strength = 0
        
        # Count signals from different indicators
        for indicator_name, data in indicators.items():
            signal = data.get('signal', 'NEUTRAL')
            
            if 'BUY' in signal:
                bullish_signals += 2 if 'STRONG' in signal else 1
            elif 'SELL' in signal:
                bearish_signals += 2 if 'STRONG' in signal else 1
        
        total_signals = bullish_signals + bearish_signals
        
        if total_signals > 0:
            bullish_ratio = bullish_signals / total_signals
            if bullish_ratio >= 0.7:
                trend = 'STRONG_BULLISH'
                signal_strength = min(bullish_ratio * 100, 95)
            elif bullish_ratio >= 0.6:
                trend = 'BULLISH'
                signal_strength = bullish_ratio * 80
            elif bullish_ratio <= 0.3:
                trend = 'STRONG_BEARISH'
                signal_strength = min((1 - bullish_ratio) * 100, 95)
            elif bullish_ratio <= 0.4:
                trend = 'BEARISH'
                signal_strength = (1 - bullish_ratio) * 80
            else:
                trend = 'NEUTRAL'
                signal_strength = 30
        else:
            trend = 'NEUTRAL'
            signal_strength = 0
        
        # Adjust for time of day (less aggressive signals near market close)
        time_factor = self._get_time_factor(current_time)
        signal_strength *= time_factor
        
        return {
            'trend': trend,
            'strength': signal_strength,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'time_factor': time_factor
        }
    
    def _get_time_factor(self, current_time: time) -> float:
        """Calculate time-based factor for signal strength."""
        # Convert time to minutes since market open
        current_minutes = current_time.hour * 60 + current_time.minute
        open_minutes = self.MARKET_OPEN.hour * 60 + self.MARKET_OPEN.minute
        close_minutes = self.LAST_ENTRY_TIME.hour * 60 + self.LAST_ENTRY_TIME.minute
        
        if current_minutes < open_minutes:
            return 0.0  # Market not open
        elif current_minutes > close_minutes:
            return 0.0  # Too late for new entries
        else:
            # Linear decrease from 1.0 at market open to 0.5 at last entry time
            session_progress = (current_minutes - open_minutes) / (close_minutes - open_minutes)
            return max(1.0 - (session_progress * 0.5), 0.5)
    
    def _generate_composite_signal(
        self, 
        indicators: Dict[str, Dict[str, Any]], 
        market_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate composite signal from multiple indicators."""
        trend = market_analysis['trend']
        strength = market_analysis['strength']
        
        # Determine primary action
        if 'STRONG_BULLISH' in trend and strength >= 70:
            action = 'BUY'
            confidence = min(strength, 90)
            reason = f"Strong bullish convergence (strength: {strength:.1f}%)"
        elif 'BULLISH' in trend and strength >= 60:
            action = 'BUY'
            confidence = min(strength, 80)
            reason = f"Bullish trend detected (strength: {strength:.1f}%)"
        elif 'STRONG_BEARISH' in trend and strength >= 70:
            action = 'SELL'
            confidence = min(strength, 90)
            reason = f"Strong bearish convergence (strength: {strength:.1f}%)"
        elif 'BEARISH' in trend and strength >= 60:
            action = 'SELL'
            confidence = min(strength, 80)
            reason = f"Bearish trend detected (strength: {strength:.1f}%)"
        else:
            action = 'HOLD'
            confidence = 30
            reason = f"Insufficient signal strength or neutral trend (strength: {strength:.1f}%)"
        
        return {
            'action': action,
            'confidence': Decimal(str(confidence)),
            'reason': reason,
            'market_analysis': market_analysis
        }
    
    def _apply_daily_trading_filters(
        self, 
        signal_result: Dict[str, Any], 
        current_time: time, 
        can_enter: bool,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Apply daily trading specific filters to signals."""
        action = signal_result['action']
        confidence = signal_result['confidence']
        reason = signal_result['reason']
        
        # Get confidence threshold - from user preferences or default
        if user:
            preferences = self._get_user_preferences(user)
            min_confidence = preferences.min_confidence_threshold
        else:
            min_confidence = self.MIN_CONFIDENCE_SCORE
        
        # Filter 1: Check if we can enter new positions
        if action in ['BUY', 'SELL'] and not can_enter:
            return {
                'action': 'HOLD',
                'confidence': Decimal('0'),
                'reason': f"Market closed or too late for new entries (current time: {current_time})"
            }
        
        # Filter 2: Minimum confidence threshold (user-specific or default)
        if confidence < min_confidence:
            return {
                'action': 'HOLD',
                'confidence': confidence,
                'reason': f"Confidence below threshold ({confidence}% < {min_confidence}%)"
            }
        
        # Filter 3: Time-based confidence adjustment
        time_factor = self._get_time_factor(current_time)
        adjusted_confidence = confidence * Decimal(str(time_factor))
        
        if adjusted_confidence < min_confidence:
            return {
                'action': 'HOLD',
                'confidence': adjusted_confidence,
                'reason': f"Time-adjusted confidence too low ({adjusted_confidence:.1f}%)"
            }
        
        return {
            'action': action,
            'confidence': adjusted_confidence,
            'reason': reason
        }
    
    def _calculate_risk_parameters(
        self, 
        stock: StockSymbol, 
        signal: Dict[str, Any],
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Calculate risk management parameters for daily trading."""
        current_price = self._get_latest_price(stock)
        
        if not current_price or signal['action'] == 'HOLD':
            return {}
        
        price = float(current_price)
        
        # Use user preferences if provided, otherwise use default values
        if user:
            preferences = self._get_user_preferences(user)
            stop_loss_pct = preferences.get_effective_stop_loss_pct()
            take_profit_pct = preferences.get_effective_take_profit_pct()
            max_position_size_pct = float(preferences.max_position_size_percentage)
        else:
            # Fallback to hardcoded values for backward compatibility
            stop_loss_pct = float(self.INTRADAY_STOP_LOSS_PCT)
            take_profit_pct = float(self.INTRADAY_TAKE_PROFIT_PCT)
            max_position_size_pct = 10.0  # 10% maximum
        
        if signal['action'] == 'BUY':
            stop_loss = price * (1 - stop_loss_pct / 100)
            take_profit = price * (1 + take_profit_pct / 100)
        else:  # SELL
            stop_loss = price * (1 + stop_loss_pct / 100)
            take_profit = price * (1 - take_profit_pct / 100)
        
        # Calculate position size based on confidence and user preferences
        confidence_factor = float(signal['confidence']) / 100
        position_size_pct = (max_position_size_pct / 100) * confidence_factor
        
        result = {
            'entry_price': price,
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'position_size_pct': round(position_size_pct * 100, 1),
            'risk_reward_ratio': abs(take_profit - price) / abs(price - stop_loss) if abs(price - stop_loss) > 0 else 0,
            'max_loss_pct': stop_loss_pct,
            'target_profit_pct': take_profit_pct
        }
        
        # Add user-specific information if available
        if user:
            preferences = self._get_user_preferences(user)
            if preferences.available_capital:
                position_size_pln = float(preferences.available_capital) * position_size_pct
                result.update({
                    'position_size_pln': round(position_size_pln, 2),
                    'max_loss_amount_pln': round(position_size_pln * (stop_loss_pct / 100), 2),
                    'target_profit_amount_pln': round(position_size_pln * (take_profit_pct / 100), 2),
                    'trading_style': preferences.trading_style,
                    'available_capital': float(preferences.available_capital)
                })
        
        return result
    
    def _time_until_market_close(self, current_time: time) -> str:
        """Calculate time remaining until market close."""
        current_minutes = current_time.hour * 60 + current_time.minute
        close_minutes = self.MARKET_CLOSE.hour * 60 + self.MARKET_CLOSE.minute
        
        if current_minutes >= close_minutes:
            return "Market closed"
        
        remaining_minutes = close_minutes - current_minutes
        hours = remaining_minutes // 60
        minutes = remaining_minutes % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def _save_trading_signal(
        self, 
        stock: StockSymbol, 
        trading_session: TradingSession, 
        signal_data: Dict[str, Any]
    ) -> None:
        """Save actionable trading signal to database."""
        try:
            # Map signal action to model choices
            signal_type_map = {
                'BUY': 'buy',
                'SELL': 'sell',
                'HOLD': 'hold'
            }
            
            signal_type = signal_type_map.get(signal_data['signal'], 'hold')
            
            # Convert Decimal values to float for JSON serialization
            def convert_decimals(obj):
                """Convert Decimal values to float for JSON serialization."""
                from datetime import datetime, date
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_decimals(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_decimals(item) for item in obj]
                return obj
            
            json_safe_signal_data = convert_decimals(signal_data)
            
            TradingSignal.objects.create(
                stock=stock,
                trading_session=trading_session,
                signal_type=signal_type,
                strength='strong' if signal_data['confidence'] >= 80 else 'moderate' if signal_data['confidence'] >= 60 else 'weak',
                confidence=signal_data['confidence'],  # Model uses 'confidence' not 'confidence_score'
                price_at_signal=Decimal(str(signal_data.get('risk_management', {}).get('entry_price', 0))),
                target_price=Decimal(str(signal_data.get('risk_management', {}).get('take_profit', 0))),
                stop_loss_price=Decimal(str(signal_data.get('risk_management', {}).get('stop_loss', 0))),
                analysis_details=json_safe_signal_data,  # Store JSON-safe signal data
                generated_by='daily_trading_system',
                is_automatic=True,
                notes=f"Intraday signal: {signal_data['reason']}"
            )
            
            logger.info(f"Saved {signal_type.upper()} signal for {stock.symbol} with {signal_data['confidence']:.1f}% confidence")
            
        except Exception as e:
            logger.error(f"Error saving trading signal for {stock.symbol}: {str(e)}")


class DailyTradingSignalService:
    """
    Service for managing daily trading signals across all monitored stocks.
    """
    
    def __init__(self):
        self.signal_generator = DailyTradingSignalGenerator()
    
    def generate_signals_for_all_monitored_stocks(self) -> Dict[str, Any]:
        """Generate signals for all monitored stocks."""
        monitored_stocks = StockSymbol.objects.filter(
            is_monitored=True,
            is_active=True
        )
        
        results = {
            'generated_at': timezone.now(),
            'total_stocks': monitored_stocks.count(),
            'signals': [],
            'summary': {
                'buy_signals': 0,
                'sell_signals': 0,
                'hold_signals': 0,
                'avg_confidence': 0
            }
        }
        
        total_confidence = 0
        
        for stock in monitored_stocks:
            try:
                signal = self.signal_generator.generate_signals_for_stock(stock)
                results['signals'].append(signal)
                
                # Update summary
                if signal['signal'] == 'BUY':
                    results['summary']['buy_signals'] += 1
                elif signal['signal'] == 'SELL':
                    results['summary']['sell_signals'] += 1
                else:
                    results['summary']['hold_signals'] += 1
                
                total_confidence += float(signal['confidence'])
                
            except Exception as e:
                logger.error(f"Error generating signal for {stock.symbol}: {str(e)}")
                results['signals'].append({
                    'stock': stock.symbol,
                    'signal': 'ERROR',
                    'confidence': 0,
                    'reason': f"Error: {str(e)}",
                    'timestamp': timezone.now()
                })
        
        # Calculate average confidence
        if results['total_stocks'] > 0:
            results['summary']['avg_confidence'] = round(
                total_confidence / results['total_stocks'], 1
            )
        
        logger.info(
            f"Generated signals for {results['total_stocks']} stocks: "
            f"{results['summary']['buy_signals']} BUY, "
            f"{results['summary']['sell_signals']} SELL, "
            f"{results['summary']['hold_signals']} HOLD"
        )
        
        return results
    
    def get_active_signals(self, signal_types: Optional[List[str]] = None) -> QuerySet:
        """Get active trading signals from database."""
        today = timezone.localtime().date()
        
        queryset = TradingSignal.objects.filter(
            trading_session__date=today,
            is_active=True,
            generated_by='daily_trading_system'  # Filter for daily trading signals
        ).select_related('stock', 'trading_session')
        
        if signal_types:
            queryset = queryset.filter(signal_type__in=signal_types)
        
        return queryset.order_by('-confidence', '-created_at')
