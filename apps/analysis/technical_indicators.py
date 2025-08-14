"""
Technical Indicators Calculation Engine for GPW Trading Advisor.

This module contains implementations of various technical analysis indicators
used for stock market analysis and trading signal generation.
"""

import pandas as pd
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Tuple, Union
from django.db.models import QuerySet
from apps.scrapers.models import StockData
from apps.core.models import StockSymbol, TradingSession
from apps.analysis.models import TechnicalIndicator, IndicatorValue
import logging

logger = logging.getLogger(__name__)


class TechnicalAnalysisEngine:
    """
    Main engine for calculating technical indicators.
    """
    
    def __init__(self):
        self.indicators = {
            'rsi': self._calculate_rsi,
            'sma': self._calculate_sma,
            'ema': self._calculate_ema,
            'macd': self._calculate_macd,
            'bollinger': self._calculate_bollinger_bands,
            'stochastic': self._calculate_stochastic,
            'williams_r': self._calculate_williams_r,
            'atr': self._calculate_atr,
        }
    
    def calculate_indicator(
        self, 
        indicator_type: str, 
        stock_data: QuerySet[StockData], 
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Calculate a specific technical indicator for given stock data.
        
        Args:
            indicator_type: Type of indicator to calculate
            stock_data: QuerySet of StockData ordered by data_timestamp
            parameters: Indicator-specific parameters
            
        Returns:
            List of calculated values with timestamps
        """
        if indicator_type not in self.indicators:
            raise ValueError(f"Unsupported indicator type: {indicator_type}")
        
        # Convert QuerySet to pandas DataFrame for easier calculations
        df = self._queryset_to_dataframe(stock_data)
        
        if df.empty:
            logger.warning(f"No data provided for {indicator_type} calculation")
            return []
        
        # Calculate the indicator
        calculator = self.indicators[indicator_type]
        results = calculator(df, parameters)
        
        return results
    
    def _queryset_to_dataframe(self, stock_data: QuerySet[StockData]) -> pd.DataFrame:
        """Convert Django QuerySet to pandas DataFrame."""
        data = []
        for record in stock_data.order_by('data_timestamp'):
            data.append({
                'timestamp': record.data_timestamp,
                'open': float(record.open_price) if record.open_price else None,
                'high': float(record.high_price) if record.high_price else None,
                'low': float(record.low_price) if record.low_price else None,
                'close': float(record.close_price) if record.close_price else None,
                'volume': float(record.volume) if record.volume else None,
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def _calculate_rsi(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Calculate Relative Strength Index (RSI).
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        
        Args:
            df: DataFrame with OHLCV data
            parameters: {'period': int} - typically 14
        """
        period = parameters.get('period', 14)
        
        if len(df) < period + 1:
            logger.warning(f"Insufficient data for RSI calculation (need {period + 1}, got {len(df)})")
            return []
        
        # Calculate price changes - explicitly convert to float
        close_values = [float(x) if x is not None and not pd.isna(x) else 0.0 for x in df['close']]
        
        # Calculate differences manually
        deltas = []
        for i in range(len(close_values)):
            if i == 0:
                deltas.append(0.0)
            else:
                deltas.append(close_values[i] - close_values[i-1])
        
        # Separate gains and losses
        gains_list = [max(0.0, d) for d in deltas]
        losses_list = [max(0.0, -d) for d in deltas]
        
        gains = pd.Series(gains_list, index=df.index)
        losses = pd.Series(losses_list, index=df.index)
        
        # Calculate average gains and losses using Wilder's smoothing method
        avg_gains = gains.rolling(window=period, min_periods=period).mean()
        avg_losses = losses.rolling(window=period, min_periods=period).mean()
        
        # For subsequent values, use Wilder's smoothing: ((prev_avg * (period-1)) + current) / period
        for i in range(period, len(df)):
            avg_gains.iloc[i] = ((avg_gains.iloc[i-1] * (period - 1)) + gains.iloc[i]) / period
            avg_losses.iloc[i] = ((avg_losses.iloc[i-1] * (period - 1)) + losses.iloc[i]) / period
        
        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        # Prepare results
        results = []
        for timestamp, value in rsi.dropna().items():
            if pd.isna(value) or np.isinf(value):
                continue
                
            results.append({
                'timestamp': timestamp,
                'value': Decimal(str(round(value, 4))),
                'value_upper': None,
                'value_lower': None,
                'value_signal': None,
            })
        
        logger.info(f"RSI calculated for {len(results)} periods with period={period}")
        return results
    
    def _calculate_sma(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Calculate Simple Moving Average (SMA).
        
        Args:
            df: DataFrame with OHLCV data
            parameters: {'period': int} - number of periods for average
        """
        period = parameters.get('period', 20)
        
        if len(df) < period:
            logger.warning(f"Insufficient data for SMA calculation (need {period}, got {len(df)})")
            return []
        
        sma = df['close'].rolling(window=period).mean()
        
        results = []
        for timestamp, value in sma.dropna().items():
            if pd.isna(value):
                continue
                
            results.append({
                'timestamp': timestamp,
                'value': Decimal(str(round(value, 4))),
                'value_upper': None,
                'value_lower': None,
                'value_signal': None,
            })
        
        logger.info(f"SMA calculated for {len(results)} periods with period={period}")
        return results
    
    def _calculate_ema(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Calculate Exponential Moving Average (EMA).
        
        Args:
            df: DataFrame with OHLCV data
            parameters: {'period': int} - number of periods for average
        """
        period = parameters.get('period', 12)
        
        if len(df) < period:
            logger.warning(f"Insufficient data for EMA calculation (need {period}, got {len(df)})")
            return []
        
        ema = df['close'].ewm(span=period, adjust=False).mean()
        
        results = []
        for timestamp, value in ema.dropna().items():
            if pd.isna(value):
                continue
                
            results.append({
                'timestamp': timestamp,
                'value': Decimal(str(round(value, 4))),
                'value_upper': None,
                'value_lower': None,
                'value_signal': None,
            })
        
        logger.info(f"EMA calculated for {len(results)} periods with period={period}")
        return results
    
    def _calculate_macd(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD Line, signal_period)
        Histogram = MACD Line - Signal Line
        
        Args:
            df: DataFrame with OHLCV data
            parameters: {'fast_period': int, 'slow_period': int, 'signal_period': int}
        """
        fast_period = parameters.get('fast_period', 12)
        slow_period = parameters.get('slow_period', 26)
        signal_period = parameters.get('signal_period', 9)
        
        min_required = slow_period + signal_period
        if len(df) < min_required:
            logger.warning(f"Insufficient data for MACD calculation (need {min_required}, got {len(df)})")
            return []
        
        # Calculate EMAs
        ema_fast = df['close'].ewm(span=fast_period).mean()
        ema_slow = df['close'].ewm(span=slow_period).mean()
        
        # Calculate MACD line
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line
        signal_line = macd_line.ewm(span=signal_period).mean()
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        results = []
        for timestamp in macd_line.dropna().index:
            if timestamp not in signal_line.dropna().index:
                continue
                
            macd_val = macd_line.loc[timestamp]
            signal_val = signal_line.loc[timestamp]
            
            if pd.isna(macd_val) or pd.isna(signal_val):
                continue
                
            results.append({
                'timestamp': timestamp,
                'value': Decimal(str(round(macd_val, 6))),  # MACD line
                'value_upper': None,
                'value_lower': None,
                'value_signal': Decimal(str(round(signal_val, 6))),  # Signal line
            })
        
        logger.info(f"MACD calculated for {len(results)} periods (fast={fast_period}, slow={slow_period}, signal={signal_period})")
        return results
    
    def _calculate_bollinger_bands(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Calculate Bollinger Bands.
        
        Middle Band = SMA(period)
        Upper Band = SMA(period) + (std_dev * Standard Deviation)
        Lower Band = SMA(period) - (std_dev * Standard Deviation)
        
        Args:
            df: DataFrame with OHLCV data
            parameters: {'period': int, 'std_dev': float}
        """
        period = parameters.get('period', 20)
        std_dev = parameters.get('std_dev', 2.0)
        
        if len(df) < period:
            logger.warning(f"Insufficient data for Bollinger Bands calculation (need {period}, got {len(df)})")
            return []
        
        # Calculate middle band (SMA)
        sma = df['close'].rolling(window=period).mean()
        
        # Calculate standard deviation
        std = df['close'].rolling(window=period).std()
        
        # Calculate upper and lower bands
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        results = []
        for timestamp in sma.dropna().index:
            sma_val = sma.loc[timestamp]
            upper_val = upper_band.loc[timestamp]
            lower_val = lower_band.loc[timestamp]
            
            if pd.isna(sma_val) or pd.isna(upper_val) or pd.isna(lower_val):
                continue
                
            results.append({
                'timestamp': timestamp,
                'value': Decimal(str(round(sma_val, 4))),  # Middle band
                'value_upper': Decimal(str(round(upper_val, 4))),  # Upper band
                'value_lower': Decimal(str(round(lower_val, 4))),  # Lower band
                'value_signal': None,
            })
        
        logger.info(f"Bollinger Bands calculated for {len(results)} periods (period={period}, std_dev={std_dev})")
        return results
    
    def _calculate_stochastic(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate Stochastic Oscillator - placeholder implementation."""
        # TODO: Implement stochastic oscillator
        logger.warning("Stochastic oscillator calculation not yet implemented")
        return []
    
    def _calculate_williams_r(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate Williams %R - placeholder implementation."""
        # TODO: Implement Williams %R
        logger.warning("Williams %R calculation not yet implemented")
        return []
    
    def _calculate_atr(self, df: pd.DataFrame, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate Average True Range - placeholder implementation."""
        # TODO: Implement ATR
        logger.warning("ATR calculation not yet implemented")
        return []


class IndicatorCalculationService:
    """
    Service for managing indicator calculations and database operations.
    """
    
    def __init__(self):
        self.engine = TechnicalAnalysisEngine()
    
    def calculate_indicators_for_stock(
        self, 
        stock: StockSymbol, 
        trading_session: Optional[TradingSession] = None,
        indicators: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """
        Calculate technical indicators for a specific stock.
        
        Args:
            stock: StockSymbol instance
            trading_session: Specific trading session (if None, uses latest available data)
            indicators: List of indicator types to calculate (if None, calculates all enabled)
            
        Returns:
            Dictionary with calculation results count per indicator
        """
        logger.info(f"Starting indicator calculations for {stock.symbol}")
        
        # Get available stock data
        stock_data = StockData.objects.filter(
            stock=stock,
            is_active=True
        ).order_by('data_timestamp')
        
        if not stock_data.exists():
            logger.warning(f"No stock data available for {stock.symbol}")
            return {}
        
        # Get indicators to calculate
        if indicators is None:
            indicator_configs = TechnicalIndicator.objects.filter(is_enabled=True)
        else:
            indicator_configs = TechnicalIndicator.objects.filter(
                indicator_type__in=indicators,
                is_enabled=True
            )
        
        results = {}
        
        for indicator_config in indicator_configs:
            try:
                # Calculate indicator values
                calculated_values = self.engine.calculate_indicator(
                    indicator_config.indicator_type,
                    stock_data,
                    indicator_config.parameters
                )
                
                # Save to database
                saved_count = self._save_indicator_values(
                    indicator_config,
                    stock,
                    calculated_values,
                    trading_session
                )
                
                results[indicator_config.indicator_type] = saved_count
                logger.info(f"Calculated and saved {saved_count} values for {indicator_config.name}")
                
            except Exception as e:
                logger.error(f"Error calculating {indicator_config.name} for {stock.symbol}: {str(e)}")
                results[indicator_config.indicator_type] = 0
        
        return results
    
    def _save_indicator_values(
        self,
        indicator: TechnicalIndicator,
        stock: StockSymbol,
        calculated_values: List[Dict[str, Any]],
        trading_session: Optional[TradingSession] = None
    ) -> int:
        """Save calculated indicator values to database."""
        saved_count = 0
        
        for value_data in calculated_values:
            timestamp = value_data['timestamp']
            
            # Get or create trading session for this timestamp
            if trading_session is None:
                session_date = timestamp.date()
                session, _ = TradingSession.objects.get_or_create(
                    date=session_date,
                    defaults={'is_active': True}
                )
            else:
                session = trading_session
            
            # Create or update indicator value
            indicator_value, created = IndicatorValue.objects.update_or_create(
                indicator=indicator,
                stock=stock,
                trading_session=session,
                defaults={
                    'value': value_data.get('value'),
                    'value_upper': value_data.get('value_upper'),
                    'value_lower': value_data.get('value_lower'),
                    'value_signal': value_data.get('value_signal'),
                    'calculation_source': 'system'
                }
            )
            
            if created or indicator_value:
                saved_count += 1
        
        return saved_count
