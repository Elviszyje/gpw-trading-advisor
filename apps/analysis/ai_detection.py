"""
AI Detection Engine for GPW Trading Advisor.
Core algorithms for anomaly detection, pattern recognition, and prediction.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Avg, Max, Min, StdDev, Count, Q

from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData
from apps.analysis.models import AnomalyAlert, PricePrediction, RiskAssessment, PatternDetection


class AnomalyDetector:
    """
    AI-powered anomaly detection for stock market data.
    """
    
    def __init__(self):
        self.default_lookback_days = 30
        self.default_confidence_threshold = 0.75
        
    def detect_price_anomalies(self, stock: StockSymbol, session: TradingSession) -> List[Dict[str, Any]]:
        """
        Detect price anomalies using statistical methods.
        """
        anomalies = []
        
        # Get recent stock data for baseline
        recent_data = self._get_recent_data(stock, session, days=self.default_lookback_days)
        if len(recent_data) < 10:  # Need sufficient data
            return anomalies
            
        # Get current session data
        current_data = StockData.objects.filter(
            stock=stock,
            trading_session=session
        ).first()
        
        if not current_data or not current_data.close_price:
            return anomalies
            
        # Calculate baseline statistics
        baseline_stats = self._calculate_baseline_stats(recent_data)
        current_price = float(current_data.close_price)
        
        # Detect price spike/drop using Z-score
        price_changes = [self._calculate_daily_return(data) for data in recent_data if data]
        if price_changes:
            mean_return = np.mean(price_changes)
            std_return = np.std(price_changes)
            
            if len(recent_data) > 1:
                yesterday_price = float(recent_data[1].close_price) if recent_data[1].close_price else current_price
                current_return = (current_price - yesterday_price) / yesterday_price
                
                if std_return > 0:
                    z_score = (current_return - mean_return) / std_return
                    
                    # Detect significant price movements
                    if abs(z_score) > 2.5:  # 2.5 standard deviations
                        anomaly_type = 'price_spike' if z_score > 0 else 'price_drop'
                        severity = min(5, max(1, int(abs(z_score))))
                        confidence = min(0.99, float(abs(z_score) / 4.0))  # Scale to 0-1
                        
                        price_change_percent = current_return * 100
                        
                        anomalies.append({
                            'type': anomaly_type,
                            'severity': severity,
                            'confidence': confidence,
                            'description': f"Unusual {anomaly_type.replace('_', ' ')} detected: {price_change_percent:.2f}% change",
                            'details': {
                                'z_score': z_score,
                                'price_change_percent': price_change_percent,
                                'baseline_mean_return': mean_return,
                                'baseline_std_return': std_return,
                                'current_price': current_price,
                                'previous_price': yesterday_price
                            },
                            'price_change_percent': price_change_percent,
                            'z_score': z_score
                        })
        
        return anomalies
    
    def detect_volume_anomalies(self, stock: StockSymbol, session: TradingSession) -> List[Dict[str, Any]]:
        """
        Detect unusual volume spikes.
        """
        anomalies = []
        
        # Get recent data for volume baseline
        recent_data = self._get_recent_data(stock, session, days=self.default_lookback_days)
        if len(recent_data) < 5:
            return anomalies
            
        current_data = StockData.objects.filter(
            stock=stock,
            trading_session=session
        ).first()
        
        if not current_data or not current_data.volume:
            return anomalies
            
        # Calculate average volume
        volumes = [float(data.volume) for data in recent_data if data.volume and data.volume > 0]
        if not volumes:
            return anomalies
            
        avg_volume = np.mean(volumes)
        current_volume = float(current_data.volume)
        
        if avg_volume > 0:
            volume_ratio = current_volume / avg_volume
            
            # Detect volume spikes
            if volume_ratio > 2.0:  # More than 200% of average volume
                severity = min(5, max(1, int(volume_ratio)))
                confidence = min(0.99, float((volume_ratio - 1) / 4.0))  # Scale to 0-1
                
                anomalies.append({
                    'type': 'volume_spike',
                    'severity': severity,
                    'confidence': confidence,
                    'description': f"Volume spike detected: {volume_ratio:.1f}x average volume ({current_volume:,.0f} vs {avg_volume:,.0f})",
                    'details': {
                        'current_volume': current_volume,
                        'average_volume': avg_volume,
                        'volume_ratio': volume_ratio,
                        'baseline_volumes': volumes[-10:]  # Last 10 days for context
                    },
                    'volume_ratio': volume_ratio
                })
        
        return anomalies
    
    def detect_pattern_breaks(self, stock: StockSymbol, session: TradingSession) -> List[Dict[str, Any]]:
        """
        Detect breaks of support/resistance levels.
        """
        anomalies = []
        
        # Get extended data for pattern analysis
        recent_data = self._get_recent_data(stock, session, days=60)
        if len(recent_data) < 20:
            return anomalies
            
        current_data = StockData.objects.filter(
            stock=stock,
            trading_session=session
        ).first()
        
        if not current_data or not current_data.close_price:
            return anomalies
            
        current_price = float(current_data.close_price)
        
        # Calculate support and resistance levels
        prices = [float(data.close_price) for data in recent_data if data.close_price]
        highs = [float(data.high_price) for data in recent_data if data.high_price]
        lows = [float(data.low_price) for data in recent_data if data.low_price]
        
        if len(prices) < 20:
            return anomalies
            
        # Simple support/resistance detection
        resistance_level = max(highs[-20:])  # Recent high
        support_level = min(lows[-20:])      # Recent low
        
        # Check for resistance break (upward)
        if current_price > resistance_level * 1.01:  # 1% above resistance
            confidence = min(0.95, (current_price - resistance_level) / resistance_level * 10)
            
            anomalies.append({
                'type': 'resistance_break',
                'severity': 4,
                'confidence': confidence,
                'description': f"Resistance break: Price {current_price:.2f} above resistance level {resistance_level:.2f}",
                'details': {
                    'current_price': current_price,
                    'resistance_level': resistance_level,
                    'break_percentage': ((current_price - resistance_level) / resistance_level) * 100
                }
            })
        
        # Check for support break (downward)
        elif current_price < support_level * 0.99:  # 1% below support
            confidence = min(0.95, (support_level - current_price) / support_level * 10)
            
            anomalies.append({
                'type': 'support_break',
                'severity': 4,
                'confidence': confidence,
                'description': f"Support break: Price {current_price:.2f} below support level {support_level:.2f}",
                'details': {
                    'current_price': current_price,
                    'support_level': support_level,
                    'break_percentage': ((support_level - current_price) / support_level) * 100
                }
            })
        
        return anomalies
    
    def process_stock_anomalies(self, stock: StockSymbol, session: TradingSession) -> int:
        """
        Process all anomaly detection for a single stock and session.
        Returns number of anomalies detected.
        """
        all_anomalies = []
        
        # Run different detection methods
        all_anomalies.extend(self.detect_price_anomalies(stock, session))
        all_anomalies.extend(self.detect_volume_anomalies(stock, session))
        all_anomalies.extend(self.detect_pattern_breaks(stock, session))
        
        # Save anomalies to database
        created_count = 0
        for anomaly in all_anomalies:
            if anomaly['confidence'] >= self.default_confidence_threshold:
                alert = AnomalyAlert.objects.create(
                    stock=stock,
                    trading_session=session,
                    anomaly_type=anomaly['type'],
                    severity=anomaly['severity'],
                    confidence_score=Decimal(str(anomaly['confidence'])),
                    description=anomaly['description'],
                    detection_details=anomaly['details'],
                    price_change_percent=Decimal(str(anomaly.get('price_change_percent', 0))),
                    volume_ratio=Decimal(str(anomaly.get('volume_ratio', 0))),
                    z_score=Decimal(str(anomaly.get('z_score', 0)))
                )
                created_count += 1
        
        return created_count
    
    def _get_recent_data(self, stock: StockSymbol, current_session: TradingSession, days: int = 30) -> List[StockData]:
        """
        Get recent stock data for analysis.
        """
        end_date = current_session.date
        start_date = end_date - timedelta(days=days)
        
        # Get one record per day (latest for each session)
        sessions = TradingSession.objects.filter(
            date__gte=start_date,
            date__lt=end_date
        ).order_by('-date')
        
        data = []
        for session in sessions:
            latest_data = StockData.objects.filter(
                stock=stock,
                trading_session=session
            ).order_by('-data_timestamp').first()
            
            if latest_data:
                data.append(latest_data)
        
        return data
    
    def _calculate_baseline_stats(self, data: List[StockData]) -> Dict[str, float]:
        """
        Calculate baseline statistical measures.
        """
        prices = [float(d.close_price) for d in data if d.close_price]
        volumes = [float(d.volume) for d in data if d.volume and d.volume > 0]
        
        return {
            'avg_price': float(np.mean(prices)) if prices else 0.0,
            'std_price': float(np.std(prices)) if prices else 0.0,
            'avg_volume': float(np.mean(volumes)) if volumes else 0.0,
            'std_volume': float(np.std(volumes)) if volumes else 0.0,
            'min_price': float(min(prices)) if prices else 0.0,
            'max_price': float(max(prices)) if prices else 0.0
        }
    
    def _calculate_daily_return(self, data: StockData) -> float:
        """
        Calculate daily return for a stock data point.
        This is a simplified version - in reality you'd need previous day data.
        """
        # For now, return 0 - this would need more sophisticated calculation
        # involving previous session's closing price
        return 0.0


class SmartAlertEngine:
    """
    AI-powered smart alert system with personalized scoring.
    """
    
    def __init__(self):
        self.base_threshold = 0.7
        
    def calculate_alert_score(self, anomaly: AnomalyAlert, user_profile: Optional[Dict] = None) -> float:
        """
        Calculate personalized alert score based on anomaly and user preferences.
        """
        base_score = float(anomaly.confidence_score)
        
        # Adjust based on severity
        severity_multiplier = {1: 0.5, 2: 0.7, 3: 1.0, 4: 1.3, 5: 1.5}
        score = base_score * severity_multiplier.get(anomaly.severity, 1.0)
        
        # Adjust based on anomaly type importance
        type_weights = {
            'price_spike': 1.2,
            'price_drop': 1.2,
            'volume_spike': 0.9,
            'resistance_break': 1.1,
            'support_break': 1.1,
            'pattern_break': 1.0
        }
        score *= type_weights.get(anomaly.anomaly_type, 1.0)
        
        # User profile adjustments (if available)
        if user_profile:
            # Adjust based on user's stock preferences
            if anomaly.stock.symbol in user_profile.get('watchlist', []):
                score *= 1.3
            
            # Adjust based on user's risk tolerance
            risk_tolerance = user_profile.get('risk_tolerance', 'medium')
            if risk_tolerance == 'high':
                score *= 0.8  # High risk users get fewer alerts
            elif risk_tolerance == 'low':
                score *= 1.2  # Low risk users get more alerts
        
        return min(1.0, score)  # Cap at 1.0
    
    def should_send_alert(self, alert_score: float, user_settings: Optional[Dict] = None) -> bool:
        """
        Determine if an alert should be sent to user.
        """
        threshold = self.base_threshold
        
        if user_settings:
            threshold = user_settings.get('alert_threshold', self.base_threshold)
        
        return alert_score >= threshold


class PatternRecognizer:
    """
    Chart and candlestick pattern recognition engine.
    """
    
    def __init__(self):
        self.min_pattern_days = 5
        
    def detect_candlestick_patterns(self, stock: StockSymbol, session: TradingSession) -> List[Dict[str, Any]]:
        """
        Detect candlestick patterns in recent data.
        """
        patterns = []
        
        # Get recent OHLC data
        recent_data = self._get_ohlc_data(stock, session, days=5)
        if len(recent_data) < 2:
            return patterns
            
        current = recent_data[0]  # Most recent
        previous = recent_data[1] if len(recent_data) > 1 else None
        
        if not current or not previous:
            return patterns
            
        # Detect Doji pattern
        doji_pattern = self._detect_doji(current)
        if doji_pattern:
            patterns.append(doji_pattern)
            
        # Detect Hammer pattern
        hammer_pattern = self._detect_hammer(current)
        if hammer_pattern:
            patterns.append(hammer_pattern)
            
        # Detect Engulfing pattern
        if previous:
            engulfing_pattern = self._detect_engulfing(current, previous)
            if engulfing_pattern:
                patterns.append(engulfing_pattern)
        
        return patterns
    
    def _get_ohlc_data(self, stock: StockSymbol, current_session: TradingSession, days: int = 10) -> List[StockData]:
        """
        Get recent OHLC data for pattern analysis.
        """
        end_date = current_session.date
        start_date = end_date - timedelta(days=days)
        
        sessions = TradingSession.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('-date')
        
        data = []
        for session in sessions:
            # Get the latest (most complete) data for each session
            session_data = StockData.objects.filter(
                stock=stock,
                trading_session=session
            ).order_by('-data_timestamp').first()
            
            if (session_data and session_data.open_price and 
                session_data.high_price and session_data.low_price and session_data.close_price):
                data.append(session_data)
        
        return data
    
    def _detect_doji(self, candle: StockData) -> Optional[Dict[str, Any]]:
        """
        Detect Doji candlestick pattern.
        """
        if not all([candle.open_price, candle.close_price, candle.high_price, candle.low_price]):
            return None
            
        open_price = float(candle.open_price or 0)
        close_price = float(candle.close_price or 0)
        high_price = float(candle.high_price or 0)
        low_price = float(candle.low_price or 0)
        
        body_size = abs(close_price - open_price)
        total_range = high_price - low_price
        
        if total_range == 0:
            return None
            
        # Doji: very small body relative to total range
        if body_size / total_range < 0.1:  # Body is less than 10% of total range
            return {
                'type': 'doji',
                'category': 'candlestick',
                'confidence': 0.8,
                'description': f"Doji pattern detected - market indecision",
                'details': {
                    'body_to_range_ratio': body_size / total_range,
                    'open': open_price,
                    'close': close_price,
                    'high': high_price,
                    'low': low_price
                }
            }
        
        return None
    
    def _detect_hammer(self, candle: StockData) -> Optional[Dict[str, Any]]:
        """
        Detect Hammer candlestick pattern.
        """
        if not all([candle.open_price, candle.close_price, candle.high_price, candle.low_price]):
            return None
            
        open_price = float(candle.open_price or 0)
        close_price = float(candle.close_price or 0)
        high_price = float(candle.high_price or 0)
        low_price = float(candle.low_price or 0)
        
        body_top = max(open_price, close_price)
        body_bottom = min(open_price, close_price)
        body_size = body_top - body_bottom
        
        upper_wick = high_price - body_top
        lower_wick = body_bottom - low_price
        total_range = high_price - low_price
        
        if total_range == 0 or body_size == 0:
            return None
            
        # Hammer: small body, long lower wick, short upper wick
        if (lower_wick > body_size * 2 and  # Lower wick at least 2x body size
            upper_wick < body_size * 0.5 and  # Upper wick less than half body size
            body_size / total_range > 0.1):   # Body is significant part of range
            
            return {
                'type': 'hammer',
                'category': 'candlestick',
                'confidence': 0.75,
                'description': f"Hammer pattern detected - potential reversal signal",
                'details': {
                    'body_size': body_size,
                    'lower_wick': lower_wick,
                    'upper_wick': upper_wick,
                    'lower_wick_to_body_ratio': lower_wick / body_size if body_size > 0 else 0
                }
            }
        
        return None
    
    def _detect_engulfing(self, current: StockData, previous: StockData) -> Optional[Dict[str, Any]]:
        """
        Detect Engulfing candlestick pattern.
        """
        if not all([current.open_price, current.close_price, previous.open_price, previous.close_price]):
            return None
            
        curr_open = float(current.open_price or 0)
        curr_close = float(current.close_price or 0)
        prev_open = float(previous.open_price or 0)
        prev_close = float(previous.close_price or 0)
        
        curr_body_top = max(curr_open, curr_close)
        curr_body_bottom = min(curr_open, curr_close)
        prev_body_top = max(prev_open, prev_close)
        prev_body_bottom = min(prev_open, prev_close)
        
        # Bullish engulfing: current green candle engulfs previous red candle
        if (curr_close > curr_open and  # Current is bullish
            prev_close < prev_open and  # Previous is bearish
            curr_body_bottom < prev_body_bottom and  # Current body engulfs previous
            curr_body_top > prev_body_top):
            
            return {
                'type': 'engulfing',
                'category': 'candlestick',
                'confidence': 0.8,
                'description': f"Bullish engulfing pattern detected",
                'details': {
                    'pattern_type': 'bullish_engulfing',
                    'current_body_size': curr_body_top - curr_body_bottom,
                    'previous_body_size': prev_body_top - prev_body_bottom
                }
            }
        
        # Bearish engulfing: current red candle engulfs previous green candle
        elif (curr_close < curr_open and  # Current is bearish
              prev_close > prev_open and  # Previous is bullish
              curr_body_bottom < prev_body_bottom and  # Current body engulfs previous
              curr_body_top > prev_body_top):
            
            return {
                'type': 'engulfing',
                'category': 'candlestick',
                'confidence': 0.8,
                'description': f"Bearish engulfing pattern detected",
                'details': {
                    'pattern_type': 'bearish_engulfing',
                    'current_body_size': curr_body_top - curr_body_bottom,
                    'previous_body_size': prev_body_top - prev_body_bottom
                }
            }
        
        return None
