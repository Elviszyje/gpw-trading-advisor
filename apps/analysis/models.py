"""
Analysis models for GPW Trading Advisor.
Technical analysis and trading signals.
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.conf import settings
from apps.core.models import SoftDeleteModel, StockSymbol, TradingSession
from apps.scrapers.models import StockData
from typing import Any, Dict, List, Optional
from decimal import Decimal


class TechnicalIndicator(SoftDeleteModel):
    """
    Configuration for technical indicators.
    """
    INDICATOR_TYPES = [
        ('sma', 'Simple Moving Average'),
        ('ema', 'Exponential Moving Average'),
        ('rsi', 'Relative Strength Index'),
        ('macd', 'MACD'),
        ('bollinger', 'Bollinger Bands'),
        ('stochastic', 'Stochastic Oscillator'),
        ('williams_r', 'Williams %R'),
        ('volume_sma', 'Volume SMA'),
        ('atr', 'Average True Range'),
        ('adx', 'Average Directional Index'),
    ]

    name = models.CharField(max_length=100)
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_TYPES)
    description = models.TextField(blank=True)
    
    # Parameters (stored as JSON for flexibility)
    parameters = models.JSONField(
        default=dict,
        help_text="Indicator parameters (e.g., {'period': 14, 'smoothing': 2})"
    )
    
    # Configuration
    is_enabled = models.BooleanField(default=True)
    calculation_order = models.PositiveIntegerField(default=100)
    
    # Thresholds for signals
    overbought_threshold = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Value above which indicator is considered overbought"
    )
    oversold_threshold = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Value below which indicator is considered oversold"
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.indicator_type})"

    @property
    def default_parameters(self) -> Dict[str, Any]:
        """Get default parameters for each indicator type."""
        defaults = {
            'sma': {'period': 20},
            'ema': {'period': 12},
            'rsi': {'period': 14},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
            'bollinger': {'period': 20, 'std_dev': 2},
            'stochastic': {'k_period': 14, 'd_period': 3},
            'williams_r': {'period': 14},
            'volume_sma': {'period': 20},
            'atr': {'period': 14},
            'adx': {'period': 14},
        }
        return defaults.get(self.indicator_type, {})

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a specific parameter value."""
        return self.parameters.get(key, self.default_parameters.get(key, default))

    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_technical_indicators'
        ordering = ['-created_at']


class AnomalyAlert(SoftDeleteModel):
    """
    AI-detected anomalies in stock behavior.
    """
    ANOMALY_TYPES = [
        ('price_spike', 'Price Spike'),
        ('price_drop', 'Price Drop'),
        ('volume_spike', 'Volume Spike'),
        ('pattern_break', 'Pattern Break'),
        ('sector_divergence', 'Sector Divergence'),
        ('support_break', 'Support Level Break'),
        ('resistance_break', 'Resistance Level Break'),
        ('unusual_activity', 'Unusual Trading Activity'),
    ]
    
    SEVERITY_LEVELS = [
        (1, 'Very Low'),
        (2, 'Low'), 
        (3, 'Medium'),
        (4, 'High'),
        (5, 'Very High'),
    ]
    
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='anomaly_alerts'
    )
    
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='anomaly_alerts'
    )
    
    anomaly_type = models.CharField(
        max_length=50,
        choices=ANOMALY_TYPES
    )
    
    severity = models.IntegerField(
        choices=SEVERITY_LEVELS,
        default=3
    )
    
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="AI confidence in anomaly detection (0-1)"
    )
    
    description = models.TextField(
        help_text="Human-readable description of the anomaly"
    )
    
    detection_details = models.JSONField(
        default=dict,
        help_text="Technical details about the anomaly detection"
    )
    
    # Anomaly metrics
    price_change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Price change percentage"
    )
    
    volume_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Volume vs average volume ratio"
    )
    
    z_score = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Statistical Z-score of the anomaly"
    )
    
    # Alert management
    is_acknowledged = models.BooleanField(
        default=False,
        help_text="Whether the alert has been acknowledged by user"
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    is_false_positive = models.BooleanField(
        default=False,
        help_text="Marked as false positive for ML training"
    )
    
    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_anomaly_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', 'anomaly_type']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['is_acknowledged', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.stock.symbol} - {self.get_anomaly_type_display()} (Severity: {self.severity})"


class PricePrediction(SoftDeleteModel):
    """
    AI-generated price direction predictions.
    """
    PREDICTION_TYPES = [
        ('next_day', 'Next Day'),
        ('next_week', 'Next Week'),
        ('next_month', 'Next Month'),
    ]
    
    DIRECTION_CHOICES = [
        ('up', 'Up'),
        ('down', 'Down'),
        ('sideways', 'Sideways'),
    ]
    
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='price_predictions'
    )
    
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='price_predictions'
    )
    
    prediction_type = models.CharField(
        max_length=20,
        choices=PREDICTION_TYPES,
        default='next_day'
    )
    
    predicted_direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES
    )
    
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Model confidence in prediction (0-1)"
    )
    
    predicted_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Predicted price value"
    )
    
    price_range_low = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Lower bound of predicted price range"
    )
    
    price_range_high = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Upper bound of predicted price range"
    )
    
    model_version = models.CharField(
        max_length=50,
        help_text="Version of ML model used for prediction"
    )
    
    features_used = models.JSONField(
        default=list,
        help_text="List of features used in prediction"
    )
    
    prediction_details = models.JSONField(
        default=dict,
        help_text="Additional prediction metadata"
    )
    
    # Validation fields (filled when prediction period expires)
    actual_direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        null=True,
        blank=True
    )
    
    actual_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    is_correct = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether the prediction was correct"
    )
    
    prediction_error = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Absolute prediction error"
    )
    
    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_price_predictions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', 'prediction_type']),
            models.Index(fields=['predicted_direction', 'confidence_score']),
            models.Index(fields=['is_correct', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.stock.symbol} - {self.get_predicted_direction_display()} ({self.confidence_score:.2%})"


class RiskAssessment(SoftDeleteModel):
    """
    AI-powered risk assessment for stocks.
    """
    RISK_LEVELS = [
        ('very_low', 'Very Low'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('very_high', 'Very High'),
    ]
    
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='risk_assessments'
    )
    
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='risk_assessments'
    )
    
    overall_risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVELS
    )
    
    overall_risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Overall risk score (0-10)"
    )
    
    # Individual risk components (0-10 scale)
    volatility_risk = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    
    liquidity_risk = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    
    market_risk = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    
    sector_risk = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    
    # Risk metrics
    beta_coefficient = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Beta coefficient vs market"
    )
    
    var_1_day = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="1-day Value at Risk (95%)"
    )
    
    var_1_week = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="1-week Value at Risk (95%)"
    )
    
    max_drawdown = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Maximum drawdown percentage"
    )
    
    risk_analysis_details = models.JSONField(
        default=dict,
        help_text="Detailed risk analysis data"
    )
    
    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_risk_assessments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', 'overall_risk_level']),
            models.Index(fields=['overall_risk_score', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.stock.symbol} - Risk: {self.get_overall_risk_level_display()} ({self.overall_risk_score}/10)"


class PatternDetection(SoftDeleteModel):
    """
    AI-detected chart and candlestick patterns.
    """
    PATTERN_TYPES = [
        # Reversal Patterns
        ('head_shoulders', 'Head and Shoulders'),
        ('inverse_head_shoulders', 'Inverse Head and Shoulders'),
        ('double_top', 'Double Top'),
        ('double_bottom', 'Double Bottom'),
        ('triple_top', 'Triple Top'),
        ('triple_bottom', 'Triple Bottom'),
        
        # Continuation Patterns
        ('ascending_triangle', 'Ascending Triangle'),
        ('descending_triangle', 'Descending Triangle'),
        ('symmetrical_triangle', 'Symmetrical Triangle'),
        ('flag', 'Flag'),
        ('pennant', 'Pennant'),
        ('wedge', 'Wedge'),
        
        # Candlestick Patterns
        ('doji', 'Doji'),
        ('hammer', 'Hammer'),
        ('shooting_star', 'Shooting Star'),
        ('engulfing', 'Engulfing'),
        ('morning_star', 'Morning Star'),
        ('evening_star', 'Evening Star'),
    ]
    
    PATTERN_CATEGORIES = [
        ('reversal', 'Reversal'),
        ('continuation', 'Continuation'),
        ('candlestick', 'Candlestick'),
    ]
    
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='pattern_detections'
    )
    
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='pattern_detections'
    )
    
    pattern_type = models.CharField(
        max_length=50,
        choices=PATTERN_TYPES
    )
    
    pattern_category = models.CharField(
        max_length=20,
        choices=PATTERN_CATEGORIES
    )
    
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Pattern detection confidence (0-1)"
    )
    
    pattern_start_date = models.DateField(
        help_text="When the pattern started forming"
    )
    
    pattern_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="When the pattern was completed"
    )
    
    is_completed = models.BooleanField(
        default=False,
        help_text="Whether the pattern is fully formed"
    )
    
    pattern_details = models.JSONField(
        default=dict,
        help_text="Technical details about the pattern"
    )
    
    # Pattern metrics
    pattern_height = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Pattern height (for target calculation)"
    )
    
    breakout_target = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Calculated breakout target price"
    )
    
    stop_loss_level = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Suggested stop loss level"
    )
    
    # Validation
    was_successful = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether the pattern played out as expected"
    )
    
    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_pattern_detections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', 'pattern_type']),
            models.Index(fields=['pattern_category', 'is_completed']),
            models.Index(fields=['confidence_score', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.stock.symbol} - {self.get_pattern_type_display()} ({self.confidence_score:.2%})"


class IndicatorValue(models.Model):
    """
    Calculated values for technical indicators.
    """
    indicator = models.ForeignKey(
        TechnicalIndicator,
        on_delete=models.CASCADE,
        related_name='values'
    )
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='indicator_values'
    )
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='indicator_values'
    )
    
    # Calculated values (different indicators may use different fields)
    value = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Primary indicator value"
    )
    value_upper = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Upper band/line (e.g., Bollinger upper)"
    )
    value_lower = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Lower band/line (e.g., Bollinger lower)"
    )
    value_signal = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Signal line (e.g., MACD signal)"
    )
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now_add=True)
    calculation_source = models.CharField(
        max_length=50,
        default='system',
        help_text="Source of calculation (system, manual, etc.)"
    )

    def __str__(self) -> str:
        return f"{self.stock.symbol} - {self.indicator.name} - {self.trading_session.date}"

    @property
    def is_overbought(self) -> bool:
        """Check if indicator value indicates overbought condition."""
        if not self.indicator.overbought_threshold or not self.value:
            return False
        return self.value >= self.indicator.overbought_threshold

    @property
    def is_oversold(self) -> bool:
        """Check if indicator value indicates oversold condition."""
        if not self.indicator.oversold_threshold or not self.value:
            return False
        return self.value <= self.indicator.oversold_threshold

    class Meta:
        db_table = 'analysis_indicator_value'
        verbose_name = 'Indicator Value'
        verbose_name_plural = 'Indicator Values'
        unique_together = ['indicator', 'stock', 'trading_session']
        ordering = ['-trading_session__date', 'stock__symbol']
        indexes = [
            models.Index(fields=['stock', 'trading_session']),
            models.Index(fields=['indicator', 'trading_session']),
        ]


class TradingSignal(SoftDeleteModel):
    """
    Generated trading signals based on analysis.
    """
    SIGNAL_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('hold', 'Hold'),
        ('watch', 'Watch'),
    ]

    STRENGTH_LEVELS = [
        ('weak', 'Weak'),
        ('moderate', 'Moderate'),
        ('strong', 'Strong'),
        ('very_strong', 'Very Strong'),
    ]

    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='trading_signals'
    )
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='trading_signals'
    )
    
    # Signal details
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES)
    strength = models.CharField(max_length=15, choices=STRENGTH_LEVELS)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Confidence level (0-100%)"
    )
    
    # Price context
    price_at_signal = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Stock price when signal was generated"
    )
    target_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Target price for the signal"
    )
    stop_loss_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Suggested stop loss price"
    )
    
    # Analysis basis
    indicators_used = models.ManyToManyField(
        TechnicalIndicator,
        blank=True,
        help_text="Technical indicators that contributed to this signal"
    )
    analysis_details = models.JSONField(
        default=dict,
        help_text="Detailed analysis data and reasoning"
    )
    
    # Signal metadata
    generated_by = models.CharField(
        max_length=100,
        default='system',
        help_text="Who/what generated this signal"
    )
    is_automatic = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    # Tracking
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    actual_outcome = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('profitable', 'Profitable'),
            ('loss', 'Loss'),
            ('break_even', 'Break Even'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    outcome_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Price at which signal was acted upon or expired"
    )
    outcome_date = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.stock.symbol} - {self.signal_type.upper()} - {self.trading_session.date}"

    @property
    def is_bullish(self) -> bool:
        """Check if signal is bullish."""
        return self.signal_type in ['buy', 'hold']

    @property
    def is_bearish(self) -> bool:
        """Check if signal is bearish."""
        return self.signal_type == 'sell'

    @property
    def potential_return(self) -> Optional[Decimal]:
        """Calculate potential return percentage."""
        if not self.target_price or not self.price_at_signal:
            return None
        
        return ((self.target_price - self.price_at_signal) / self.price_at_signal) * 100

    @property
    def risk_percentage(self) -> Optional[Decimal]:
        """Calculate risk percentage (stop loss)."""
        if not self.stop_loss_price or not self.price_at_signal:
            return None
        
        return ((self.price_at_signal - self.stop_loss_price) / self.price_at_signal) * 100

    @property
    def risk_reward_ratio(self) -> Optional[Decimal]:
        """Calculate risk/reward ratio."""
        potential_return = self.potential_return
        risk_percent = self.risk_percentage
        
        if not potential_return or not risk_percent or risk_percent == 0:
            return None
        
        return abs(potential_return / risk_percent)

    def mark_as_sent(self) -> None:
        """Mark signal as sent to users."""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent', 'sent_at'])

    def update_outcome(self, outcome: str, price: Decimal, date: Optional[timezone.datetime] = None) -> None:
        """Update signal outcome."""
        self.actual_outcome = outcome
        self.outcome_price = price
        self.outcome_date = date or timezone.now()
        self.save(update_fields=['actual_outcome', 'outcome_price', 'outcome_date'])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_trading_signal'
        verbose_name = 'Trading Signal'
        verbose_name_plural = 'Trading Signals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', 'signal_type', 'created_at']),
            models.Index(fields=['trading_session', 'signal_type']),
            models.Index(fields=['is_sent', 'created_at']),
        ]


class MarketAnalysis(SoftDeleteModel):
    """
    Overall market analysis and sentiment.
    """
    MARKET_SENTIMENT = [
        ('very_bearish', 'Very Bearish'),
        ('bearish', 'Bearish'),
        ('neutral', 'Neutral'),
        ('bullish', 'Bullish'),
        ('very_bullish', 'Very Bullish'),
    ]

    trading_session = models.OneToOneField(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='market_analysis'
    )
    
    # Overall sentiment
    market_sentiment = models.CharField(max_length=20, choices=MARKET_SENTIMENT)
    sentiment_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
        help_text="Sentiment score (-100 to +100)"
    )
    
    # Market statistics
    total_stocks_analyzed = models.PositiveIntegerField(default=0)
    bullish_signals_count = models.PositiveIntegerField(default=0)
    bearish_signals_count = models.PositiveIntegerField(default=0)
    neutral_signals_count = models.PositiveIntegerField(default=0)
    
    # Volume analysis
    market_volume = models.BigIntegerField(null=True, blank=True)
    volume_trend = models.CharField(
        max_length=20,
        choices=[
            ('increasing', 'Increasing'),
            ('decreasing', 'Decreasing'),
            ('stable', 'Stable'),
        ],
        null=True,
        blank=True
    )
    
    # Key insights
    key_insights = models.JSONField(default=list, help_text="List of key market insights")
    top_gainers = models.JSONField(default=list, help_text="Top gaining stocks")
    top_losers = models.JSONField(default=list, help_text="Top losing stocks")
    most_active = models.JSONField(default=list, help_text="Most active stocks by volume")
    
    # Analysis metadata
    analysis_version = models.CharField(max_length=20, default='1.0')
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # Summary
    summary = models.TextField(help_text="Human-readable market summary")

    def __str__(self) -> str:
        return f"Market Analysis - {self.trading_session.date} ({self.market_sentiment})"

    @property
    def total_signals(self) -> int:
        """Get total number of signals."""
        return self.bullish_signals_count + self.bearish_signals_count + self.neutral_signals_count

    @property
    def bullish_percentage(self) -> float:
        """Get percentage of bullish signals."""
        total = self.total_signals
        if total == 0:
            return 0.0
        return (self.bullish_signals_count / total) * 100

    @property
    def bearish_percentage(self) -> float:
        """Get percentage of bearish signals."""
        total = self.total_signals
        if total == 0:
            return 0.0
        return (self.bearish_signals_count / total) * 100

    def add_insight(self, insight: str) -> None:
        """Add a key insight to the analysis."""
        if isinstance(self.key_insights, list):
            self.key_insights.append(insight)
        else:
            self.key_insights = [insight]
        self.save(update_fields=['key_insights'])

    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_market_analysis'
        verbose_name = 'Market Analysis'
        verbose_name_plural = 'Market Analyses'
        ordering = ['-trading_session__date']


class PredictionResult(SoftDeleteModel):
    """
    ML-generated prediction results with feedback tracking.
    """
    PREDICTION_TYPES = [
        ('intraday_price', 'Intraday Price'),
        ('price_direction', 'Price Direction'),
        ('anomaly_detection', 'Anomaly Detection'),
        ('volume_prediction', 'Volume Prediction'),
    ]
    
    stock = models.ForeignKey(
        StockSymbol,
        on_delete=models.CASCADE,
        related_name='ml_predictions'
    )
    
    trading_session = models.ForeignKey(
        TradingSession,
        on_delete=models.CASCADE,
        related_name='ml_predictions'
    )
    
    prediction_type = models.CharField(
        max_length=30,
        choices=PREDICTION_TYPES,
        default='intraday_price'
    )
    
    predicted_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    predicted_change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    confidence = models.FloatField(
        help_text="Model confidence score (0.0 - 1.0)"
    )
    
    prediction_horizon_hours = models.IntegerField(
        default=4,
        help_text="Prediction horizon in hours"
    )
    
    actual_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Actual price outcome for accuracy tracking"
    )
    
    accuracy_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Calculated accuracy score (0.0 - 1.0)"
    )
    
    user_feedback = models.JSONField(
        default=dict,
        blank=True,
        help_text="User feedback for model improvement"
    )
    
    model_version = models.CharField(
        max_length=20,
        default='v1.0',
        help_text="ML model version used"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    def __str__(self) -> str:
        return f"ML Prediction: {self.stock.symbol} - {self.prediction_type} ({self.created_at.date()})"
    
    @property
    def is_accurate(self) -> bool:
        """Check if prediction was accurate (>70% accuracy)."""
        return self.accuracy_score is not None and self.accuracy_score >= 0.7
    
    def calculate_accuracy(self) -> Optional[float]:
        """Calculate prediction accuracy if actual outcome is available."""
        if not self.actual_price or not self.predicted_price:
            return None
        
        try:
            predicted = float(self.predicted_price)
            actual = float(self.actual_price)
            
            # Calculate percentage error
            error = abs(predicted - actual) / actual
            
            # Convert to accuracy score
            accuracy = max(0.0, 1.0 - error)
            
            self.accuracy_score = accuracy
            self.save(update_fields=['accuracy_score'])
            
            return accuracy
            
        except (ValueError, ZeroDivisionError):
            return None
    
    class Meta(SoftDeleteModel.Meta):
        db_table = 'analysis_prediction_result'
        verbose_name = 'ML Prediction Result'
        verbose_name_plural = 'ML Prediction Results'
        ordering = ['-created_at']


class TimeWeightConfiguration(models.Model):
    """
    Configuration for time-weighted news analysis for intraday trading
    """
    TRADING_STYLE_CHOICES = [
        ('intraday', 'Intraday Trading'),
        ('swing', 'Swing Trading'),
        ('position', 'Position Trading'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    trading_style = models.CharField(max_length=20, choices=TRADING_STYLE_CHOICES)
    
    # Time decay parameters
    half_life_minutes = models.IntegerField(
        default=120, 
        help_text="Time in minutes for news impact to decay by 50%"
    )
    
    # Weight multipliers for different time periods (all should sum to 1.0)
    last_15min_weight = models.FloatField(
        default=0.4, 
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for news from last 15 minutes"
    )
    last_1hour_weight = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for news from last 1 hour"
    )
    last_4hour_weight = models.FloatField(
        default=0.2,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for news from last 4 hours"
    )
    today_weight = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weight for older news from today"
    )
    
    # Impact modifiers for different scenarios
    breaking_news_multiplier = models.FloatField(
        default=2.0,
        help_text="Multiplier for high-impact breaking news"
    )
    market_hours_multiplier = models.FloatField(
        default=1.5,
        help_text="Multiplier for news published during market hours"
    )
    pre_market_multiplier = models.FloatField(
        default=1.2,
        help_text="Multiplier for news published in pre-market hours"
    )
    
    # Minimum impact threshold
    min_impact_threshold = models.FloatField(
        default=0.05,
        help_text="Minimum impact score to consider news relevant"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analysis_time_weight_configs'
        verbose_name = 'Time Weight Configuration'
        verbose_name_plural = 'Time Weight Configurations'
        
    def clean(self):
        """Validate that weights sum to approximately 1.0"""
        total_weight = (
            self.last_15min_weight + 
            self.last_1hour_weight + 
            self.last_4hour_weight + 
            self.today_weight
        )
        if abs(total_weight - 1.0) > 0.05:  # Allow 5% tolerance
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f"Time weights must sum to 1.0 (currently {total_weight:.2f})"
            )
    
    def __str__(self):
        return f"{self.name} ({self.trading_style})"
