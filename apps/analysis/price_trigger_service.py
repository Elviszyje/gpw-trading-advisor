"""
Price-Based Trigger Service for Real-Time Analysis Activation

This service monitors stock price changes and triggers analysis when significant
market movements occur, providing more responsive trading signal generation.
"""

import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, F
from django.conf import settings

from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData
from apps.analysis.models import TradingSignal, TimeWeightConfiguration
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator

logger = logging.getLogger(__name__)


class PriceBasedTriggerService:
    """
    Service that monitors price changes and triggers real-time analysis
    when significant market movements are detected.
    """
    
    def __init__(self):
        self.price_change_threshold = Decimal('2.0')  # 2% change triggers analysis
        self.volume_spike_threshold = Decimal('1.5')  # 150% of average volume
        self.breakout_threshold = Decimal('1.0')  # 1% beyond support/resistance
        self.monitoring_window_minutes = 15  # Look back 15 minutes for changes
        
    def check_for_trigger_events(self) -> Dict:
        """
        Main method to check for events that should trigger immediate analysis.
        Returns summary of triggers found and actions taken.
        """
        try:
            logger.info("[PriceTrigger] Starting price-based trigger check")
            
            # Get monitored stocks
            monitored_stocks = StockSymbol.objects.filter(is_monitored=True)
            trigger_events = []
            signals_generated = 0
            
            current_time = timezone.now()
            
            for stock in monitored_stocks:
                # Check each type of trigger for this stock
                triggers = self._analyze_stock_triggers(stock, current_time)
                
                if triggers['has_triggers']:
                    trigger_events.append({
                        'stock': stock.symbol,
                        'triggers': triggers,
                        'timestamp': current_time
                    })
                    
                    # Generate immediate signals if significant triggers found
                    if self._should_generate_immediate_signal(triggers):
                        signal_result = self._generate_priority_signal(stock, triggers)
                        if signal_result['success']:
                            signals_generated += 1
                            logger.info(
                                f"[PriceTrigger] Generated priority signal for {stock.symbol}: "
                                f"{signal_result['signal_type']}"
                            )
            
            return {
                'success': True,
                'timestamp': current_time,
                'monitored_stocks': monitored_stocks.count(),
                'trigger_events': len(trigger_events),
                'signals_generated': signals_generated,
                'events': trigger_events
            }
            
        except Exception as e:
            logger.error(f"[PriceTrigger] Error checking trigger events: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now()
            }
    
    def _analyze_stock_triggers(self, stock: StockSymbol, current_time: datetime) -> Dict:
        """
        Analyze a specific stock for trigger conditions.
        """
        triggers = {
            'has_triggers': False,
            'price_change_trigger': None,
            'volume_trigger': None,
            'breakout_trigger': None,
            'momentum_trigger': None
        }
        
        # Get recent stock data for analysis
        cutoff_time = current_time - timedelta(minutes=int(self.monitoring_window_minutes))
        
        recent_data = StockData.objects.filter(
            stock=stock,
            data_timestamp__gte=cutoff_time
        ).order_by('-data_timestamp')[:20]
        
        if recent_data.count() < 2:
            return triggers
        
        latest_data = recent_data[0]
        previous_data = recent_data[1] if recent_data.count() > 1 else None
        
        if not previous_data:
            return triggers
            
        logger.debug(f"[PriceTrigger] Analyzing {stock.symbol}: latest={latest_data.close_price}, previous={previous_data.close_price}")
            
        # 1. Check for significant price change
        price_change = self._calculate_price_change_trigger(latest_data, previous_data)
        if price_change:
            triggers['price_change_trigger'] = price_change
            triggers['has_triggers'] = True
            logger.debug(f"[PriceTrigger] Price trigger found for {stock.symbol}: {price_change['change_percent']:.2f}%")
        
        # 2. Check for volume spike
        volume_trigger = self._calculate_volume_trigger(stock, latest_data, list(recent_data))
        if volume_trigger:
            triggers['volume_trigger'] = volume_trigger
            triggers['has_triggers'] = True
        
        # 3. Check for breakout patterns
        breakout_trigger = self._calculate_breakout_trigger(stock, latest_data, list(recent_data))
        if breakout_trigger:
            triggers['breakout_trigger'] = breakout_trigger
            triggers['has_triggers'] = True
        
        # 4. Check for momentum shifts
        momentum_trigger = self._calculate_momentum_trigger(list(recent_data))
        if momentum_trigger:
            triggers['momentum_trigger'] = momentum_trigger
            triggers['has_triggers'] = True
            
        return triggers
    
    def _calculate_price_change_trigger(self, latest: StockData, previous: StockData) -> Optional[Dict]:
        """
        Calculate if price change exceeds threshold for trigger activation.
        """
        if not latest.close_price or not previous.close_price:
            return None
            
        price_change_pct = (
            (latest.close_price - previous.close_price) / previous.close_price * 100
        )
        
        logger.debug(f"[PriceTrigger] Price change calculation: {latest.close_price} -> {previous.close_price} = {price_change_pct:.2f}%")
        
        if abs(price_change_pct) >= self.price_change_threshold:
            return {
                'type': 'price_change',
                'change_percent': float(price_change_pct),
                'threshold': float(self.price_change_threshold),
                'direction': 'up' if price_change_pct > 0 else 'down',
                'current_price': float(latest.close_price),
                'previous_price': float(previous.close_price),
                'triggered_at': latest.data_timestamp
            }
        
        return None
    
    def _calculate_volume_trigger(self, stock: StockSymbol, latest: StockData, recent_data: List[StockData]) -> Optional[Dict]:
        """
        Calculate if volume spike exceeds threshold for trigger activation.
        """
        if not latest.volume or latest.volume <= 0:
            return None
            
        # Calculate average volume from recent data (excluding current)
        valid_volumes = [
            data.volume for data in recent_data[1:10] 
            if data.volume and data.volume > 0
        ]
        
        if len(valid_volumes) < 3:
            return None
            
        avg_volume = sum(valid_volumes) / len(valid_volumes)
        volume_ratio = latest.volume / avg_volume
        
        if volume_ratio >= self.volume_spike_threshold:
            return {
                'type': 'volume_spike',
                'current_volume': int(latest.volume),
                'average_volume': int(avg_volume),
                'volume_ratio': float(volume_ratio),
                'threshold': float(self.volume_spike_threshold),
                'triggered_at': latest.data_timestamp
            }
        
        return None
    
    def _calculate_breakout_trigger(self, stock: StockSymbol, latest: StockData, recent_data: List[StockData]) -> Optional[Dict]:
        """
        Calculate if price breakout occurs (simple support/resistance levels).
        """
        if len(recent_data) < 10 or not latest.close_price:
            return None
            
        # Calculate recent highs and lows for simple support/resistance
        recent_prices = [data.close_price for data in recent_data if data.close_price]
        
        if len(recent_prices) < 5:
            return None
            
        recent_high = max(recent_prices[1:])  # Exclude current price
        recent_low = min(recent_prices[1:])   # Exclude current price
        current_price = latest.close_price
        
        # Check for breakout above resistance
        resistance_breakout_threshold = recent_high * (1 + self.breakout_threshold / 100)
        if current_price >= resistance_breakout_threshold:
            return {
                'type': 'resistance_breakout',
                'current_price': float(current_price),
                'resistance_level': float(recent_high),
                'breakout_threshold': float(resistance_breakout_threshold),
                'breakout_percent': float(self.breakout_threshold),
                'triggered_at': latest.data_timestamp
            }
        
        # Check for breakdown below support
        support_breakdown_threshold = recent_low * (1 - self.breakout_threshold / 100)
        if current_price <= support_breakdown_threshold:
            return {
                'type': 'support_breakdown',
                'current_price': float(current_price),
                'support_level': float(recent_low),
                'breakdown_threshold': float(support_breakdown_threshold),
                'breakdown_percent': float(self.breakout_threshold),
                'triggered_at': latest.data_timestamp
            }
        
        return None
    
    def _calculate_momentum_trigger(self, recent_data: List[StockData]) -> Optional[Dict]:
        """
        Calculate momentum shifts that might trigger immediate analysis.
        """
        if len(recent_data) < 6:
            return None
            
        # Calculate short-term momentum (3-period moving average trend)
        prices = [data.close_price for data in recent_data[:6] if data.close_price]
        
        if len(prices) < 6:
            return None
            
        # Calculate 3-period moving averages
        ma1 = Decimal(str(sum(prices[:3]) / 3))  # Most recent 3 periods
        ma2 = Decimal(str(sum(prices[3:6]) / 3))  # Previous 3 periods
        
        momentum_change_pct = (ma1 - ma2) / ma2 * Decimal('100')
        
        # Trigger on significant momentum shift (> 1.5%)
        if abs(momentum_change_pct) >= 1.5:
            return {
                'type': 'momentum_shift',
                'momentum_change_percent': float(momentum_change_pct),
                'direction': 'accelerating_up' if momentum_change_pct > 0 else 'accelerating_down',
                'recent_ma': float(ma1),
                'previous_ma': float(ma2),
                'triggered_at': recent_data[0].data_timestamp
            }
        
        return None
    
    def _should_generate_immediate_signal(self, triggers: Dict) -> bool:
        """
        Determine if triggers are significant enough to generate immediate signal.
        """
        # Generate immediate signal if:
        # 1. Price change > 2.5% OR
        # 2. Volume spike > 2x average AND price change > 1% OR  
        # 3. Any breakout trigger OR
        # 4. Strong momentum shift (> 2%)
        
        price_trigger = triggers.get('price_change_trigger')
        volume_trigger = triggers.get('volume_trigger')
        breakout_trigger = triggers.get('breakout_trigger')
        momentum_trigger = triggers.get('momentum_trigger')
        
        # High priority price change - Lower threshold for aggressive testing
        if price_trigger and abs(price_trigger['change_percent']) >= 1.8:  # Lowered from 2.5% to 1.8%
            logger.debug(f"[PriceTrigger] Immediate signal triggered by price change: {price_trigger['change_percent']:.2f}%")
            return True
            
        # Volume + price combination
        if (volume_trigger and volume_trigger['volume_ratio'] >= 2.0 and
            price_trigger and abs(price_trigger['change_percent']) >= 1.0):
            return True
            
        # Any breakout
        if breakout_trigger:
            return True
            
        # Strong momentum shift
        if (momentum_trigger and 
            abs(momentum_trigger['momentum_change_percent']) >= 2.0):
            return True
            
        return False
    
    def _generate_priority_signal(self, stock: StockSymbol, triggers: Dict) -> Dict:
        """
        Generate priority trading signal based on triggers.
        """
        try:
            # Get current trading session
            current_session = TradingSession.objects.filter(
                date=timezone.now().date()
            ).first()
            
            if not current_session:
                # Create session if it doesn't exist
                current_session = TradingSession.objects.create(
                    date=timezone.now().date(),
                    status='active'
                )
            
            # Use basic signal generator for priority signals
            generator = DailyTradingSignalGenerator()
            
            # Generate signal with priority context  
            signal_result = generator.generate_signals_for_stock(
                stock=stock,
                trading_session=current_session
            )
            
            # Check if signal was generated and actionable
            if signal_result.get('signal') in ['BUY', 'SELL']:
                # Find the newly created signal
                recent_signals = TradingSignal.objects.filter(
                    stock=stock,
                    trading_session=current_session,
                    created_at__gte=timezone.now() - timedelta(minutes=1),
                    signal_type__in=['buy', 'sell']
                ).order_by('-created_at')
                
                if recent_signals.exists():
                    signal = recent_signals.first()
                    if signal:  # Check if signal exists
                        # Add priority signal info to notes
                        trigger_types = [t['type'] for t in triggers.values() if t and isinstance(t, dict)]
                        priority_info = (
                            f"Priority signal triggered by: {', '.join(trigger_types)}\n"
                            f"Trigger timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"{signal.notes if signal.notes else ''}"
                        )
                        signal.notes = priority_info.strip()
                        signal.save()
                        
                        logger.info(f"[PriceTrigger] Marked signal {signal.pk} as priority signal")
                
                return {
                    'success': True,
                    'signal_type': signal_result['signal'],
                    'confidence': signal_result.get('confidence', 0),
                    'stock': stock.symbol
                }
            else:
                return {
                    'success': False,
                    'error': f"No actionable signal generated - got {signal_result.get('signal', 'UNKNOWN')}",
                    'stock': stock.symbol,
                    'reason': signal_result.get('reason', 'No reason provided')
                }
            
        except Exception as e:
            logger.error(f"[PriceTrigger] Error generating priority signal for {stock.symbol}: {e}")
            return {
                'success': False,
                'error': str(e),
                'stock': stock.symbol
            }


def run_price_trigger_analysis() -> Dict:
    """
    Convenience function to run price trigger analysis.
    Can be called from management commands or Celery tasks.
    """
    service = PriceBasedTriggerService()
    return service.check_for_trigger_events()


# Configuration class for customizing trigger thresholds
class PriceTriggerConfig:
    """
    Configuration for price trigger thresholds and settings.
    """
    
    @staticmethod
    def get_config(profile: str = 'default') -> Dict:
        """
        Get trigger configuration for different profiles.
        
        Profiles:
        - aggressive: Lower thresholds, more sensitive
        - default: Balanced thresholds
        - conservative: Higher thresholds, less sensitive
        """
        configs = {
            'aggressive': {
                'price_change_threshold': 1.5,
                'volume_spike_threshold': 1.3,
                'breakout_threshold': 0.8,
                'monitoring_window_minutes': 10
            },
            'default': {
                'price_change_threshold': 2.0,
                'volume_spike_threshold': 1.5,
                'breakout_threshold': 1.0,
                'monitoring_window_minutes': 15
            },
            'conservative': {
                'price_change_threshold': 3.0,
                'volume_spike_threshold': 2.0,
                'breakout_threshold': 1.5,
                'monitoring_window_minutes': 20
            }
        }
        
        return configs.get(profile, configs['default'])
