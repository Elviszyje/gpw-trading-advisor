"""
Time-Weighted News Analysis for Intraday Trading
===============================================

This module provides sophisticated time-weighted sentiment analysis where
recent news gets higher impact for intraday trading decisions.
"""

from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import math
from apps.news.models import NewsArticleModel, NewsSource
from apps.core.models import StockSymbol
from apps.analysis.models import TimeWeightConfiguration


class NewsTimeWeightAnalyzer:
    """
    Advanced time-weighted news sentiment analyzer for intraday trading
    """
    
    def __init__(self, config_name: str = "intraday_default"):
        try:
            self.config = TimeWeightConfiguration.objects.get(
                name=config_name, is_active=True
            )
        except TimeWeightConfiguration.DoesNotExist:
            # Create default intraday config if not exists
            self.config = self._create_default_intraday_config()
    
    def _create_default_intraday_config(self) -> TimeWeightConfiguration:
        """Create default intraday trading configuration"""
        config = TimeWeightConfiguration.objects.create(
            name="intraday_default",
            trading_style="intraday",
            half_life_minutes=120,
            last_15min_weight=0.4,
            last_1hour_weight=0.3,
            last_4hour_weight=0.2,
            today_weight=0.1,
            breaking_news_multiplier=2.0,
            market_hours_multiplier=1.5,
            pre_market_multiplier=1.2,
            min_impact_threshold=0.05
        )
        return config
    
    def calculate_time_weight(self, news_time: datetime, current_time: Optional[datetime] = None) -> float:
        """
        Calculate time-based weight for news article using exponential decay
        
        Args:
            news_time: When the news was published
            current_time: Current time (defaults to now)
            
        Returns:
            float: Weight between 0.0 and 1.0
        """
        if current_time is None:
            current_time = timezone.now()
        
        # Calculate time difference in minutes
        time_diff = (current_time - news_time).total_seconds() / 60
        
        if time_diff < 0:
            time_diff = 0  # Future news (shouldn't happen, but handle it)
        
        # Exponential decay: weight = e^(-λt) where λ = ln(2)/half_life
        decay_constant = math.log(2) / self.config.half_life_minutes
        base_weight = math.exp(-decay_constant * time_diff)
        
        # Apply time period weights
        if time_diff <= 15:
            period_weight = self.config.last_15min_weight
        elif time_diff <= 60:
            period_weight = self.config.last_1hour_weight
        elif time_diff <= 240:  # 4 hours
            period_weight = self.config.last_4hour_weight
        else:
            period_weight = self.config.today_weight
        
        return base_weight * period_weight
    
    def calculate_market_timing_multiplier(self, news_time: datetime) -> float:
        """
        Calculate multiplier based on when news was published relative to market hours
        
        Args:
            news_time: When the news was published
            
        Returns:
            float: Multiplier for news impact
        """
        hour = news_time.hour
        
        # Market hours: 9:00 - 17:30 CET
        if 9 <= hour < 17 or (hour == 17 and news_time.minute <= 30):
            return self.config.market_hours_multiplier
        # Pre-market: 7:00 - 9:00 CET
        elif 7 <= hour < 9:
            return self.config.pre_market_multiplier
        # After hours
        else:
            return 1.0
    
    def calculate_weighted_sentiment(
        self, 
        stock: StockSymbol, 
        current_time: Optional[datetime] = None,
        lookback_hours: int = 24
    ) -> Dict[str, float]:
        """
        Calculate time-weighted sentiment score for a stock
        
        Args:
            stock: Stock symbol to analyze
            current_time: Current time (defaults to now)
            lookback_hours: How many hours to look back for news
            
        Returns:
            Dict containing weighted sentiment metrics
        """
        if current_time is None:
            current_time = timezone.now()
        
        # Get news from lookback period
        start_time = current_time - timedelta(hours=lookback_hours)
        
        # Query news mentioning this stock
        news_articles = NewsArticleModel.objects.filter(
            mentioned_stocks=stock,
            published_date__gte=start_time,
            published_date__lte=current_time,
            sentiment_score__isnull=False
        ).order_by('-published_date')
        
        if not news_articles.exists():
            return self._get_neutral_sentiment_result()
        
        # Calculate weighted metrics
        weighted_sentiments = []
        total_weights = 0.0
        recent_news_count = 0
        breaking_news_impact = 0.0
        
        for article in news_articles:
            # Base time weight
            time_weight = self.calculate_time_weight(
                article.published_date, current_time
            )
            
            # Market timing multiplier
            timing_multiplier = self.calculate_market_timing_multiplier(
                article.published_date
            )
            
            # Breaking news multiplier
            breaking_multiplier = 1.0
            if (article.market_impact == 'high' and 
                article.impact_score and article.impact_score > 0.7):
                breaking_multiplier = self.config.breaking_news_multiplier
                breaking_news_impact += article.impact_score * time_weight
            
            # Final weight
            final_weight = time_weight * timing_multiplier * breaking_multiplier
            
            # Skip news with too low impact
            if final_weight < self.config.min_impact_threshold:
                continue
            
            # Ensure sentiment_score is not None before multiplying
            if article.sentiment_score is not None:
                weighted_sentiments.append(article.sentiment_score * final_weight)
                total_weights += final_weight            # Count recent news (last 4 hours)
            if (current_time - article.published_date).total_seconds() <= 14400:  # 4 hours
                recent_news_count += 1
        
        # Calculate final weighted sentiment
        if total_weights > 0:
            weighted_sentiment_score = sum(weighted_sentiments) / total_weights
        else:
            weighted_sentiment_score = 0.0
        
        # Calculate momentum (recent vs older sentiment)
        momentum = self._calculate_sentiment_momentum(
            news_articles, current_time
        )
        
        return {
            'weighted_sentiment_score': weighted_sentiment_score,
            'total_weight': total_weights,
            'news_count': len(weighted_sentiments),
            'recent_news_count': recent_news_count,
            'breaking_news_impact': breaking_news_impact,
            'sentiment_momentum': momentum,
            'confidence': min(1.0, total_weights / 2.0),  # Normalize confidence
        }
    
    def _calculate_sentiment_momentum(
        self, 
        news_articles, 
        current_time: datetime
    ) -> float:
        """
        Calculate sentiment momentum by comparing recent vs older news
        
        Returns:
            float: Momentum score (-1.0 to 1.0)
        """
        cutoff_time = current_time - timedelta(hours=2)
        
        recent_sentiments = []
        older_sentiments = []
        
        for article in news_articles:
            if article.published_date >= cutoff_time:
                recent_sentiments.append(article.sentiment_score)
            else:
                older_sentiments.append(article.sentiment_score)
        
        if not recent_sentiments or not older_sentiments:
            return 0.0  # Not enough data for momentum
        
        recent_avg = np.mean(recent_sentiments)
        older_avg = np.mean(older_sentiments)
        
        return float(recent_avg - older_avg)
    
    def _get_neutral_sentiment_result(self) -> Dict[str, float]:
        """Return neutral sentiment result when no news is found"""
        return {
            'weighted_sentiment_score': 0.0,
            'total_weight': 0.0,
            'news_count': 0,
            'recent_news_count': 0,
            'breaking_news_impact': 0.0,
            'sentiment_momentum': 0.0,
            'confidence': 0.0,
        }
    
    def get_intraday_sentiment_signal(
        self, 
        stock: StockSymbol, 
        current_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get intraday trading signal based on time-weighted sentiment
        
        Returns:
            Dict containing trading signal and metadata
        """
        sentiment_data = self.calculate_weighted_sentiment(
            stock, current_time, lookback_hours=24
        )
        
        # Determine signal strength
        score = sentiment_data['weighted_sentiment_score']
        momentum = sentiment_data['sentiment_momentum']
        confidence = sentiment_data['confidence']
        
        # Signal logic for intraday trading
        if confidence < 0.2:
            signal = 'NEUTRAL'
            signal_strength = 0.0
        elif score > 0.3 and momentum > 0.1:
            signal = 'STRONG_BUY'
            signal_strength = min(1.0, (score + momentum) * confidence)
        elif score > 0.1 and momentum > 0.0:
            signal = 'BUY'
            signal_strength = (score + momentum * 0.5) * confidence
        elif score < -0.3 and momentum < -0.1:
            signal = 'STRONG_SELL'
            signal_strength = min(1.0, abs(score + momentum) * confidence)
        elif score < -0.1 and momentum < 0.0:
            signal = 'SELL'
            signal_strength = abs(score + momentum * 0.5) * confidence
        else:
            signal = 'NEUTRAL'
            signal_strength = 0.0
        
        return {
            'signal': signal,
            'signal_strength': signal_strength,
            'sentiment_data': sentiment_data,
            'analysis_time': current_time or timezone.now(),
        }


# Create default configurations
def create_default_configurations():
    """Create default time weight configurations for different trading styles"""
    
    configurations = [
        {
            'name': 'intraday_aggressive',
            'trading_style': 'intraday',
            'half_life_minutes': 90,
            'last_15min_weight': 0.5,
            'last_1hour_weight': 0.3,
            'last_4hour_weight': 0.15,
            'today_weight': 0.05,
            'breaking_news_multiplier': 2.5,
            'market_hours_multiplier': 1.8,
            'pre_market_multiplier': 1.4,
            'min_impact_threshold': 0.03,
        },
        {
            'name': 'intraday_conservative',
            'trading_style': 'intraday',
            'half_life_minutes': 180,
            'last_15min_weight': 0.3,
            'last_1hour_weight': 0.3,
            'last_4hour_weight': 0.25,
            'today_weight': 0.15,
            'breaking_news_multiplier': 1.5,
            'market_hours_multiplier': 1.2,
            'pre_market_multiplier': 1.1,
            'min_impact_threshold': 0.1,
        },
        {
            'name': 'swing_trading',
            'trading_style': 'swing',
            'half_life_minutes': 720,  # 12 hours
            'last_15min_weight': 0.2,
            'last_1hour_weight': 0.25,
            'last_4hour_weight': 0.3,
            'today_weight': 0.25,
            'breaking_news_multiplier': 1.8,
            'market_hours_multiplier': 1.3,
            'pre_market_multiplier': 1.15,
            'min_impact_threshold': 0.07,
        }
    ]
    
    for config_data in configurations:
        TimeWeightConfiguration.objects.get_or_create(
            name=config_data['name'],
            defaults=config_data
        )
