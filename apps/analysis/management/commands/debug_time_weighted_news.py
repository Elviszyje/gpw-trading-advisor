"""
Management command to debug time-weighted news analysis
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from apps.core.models import StockSymbol
from apps.news.models import NewsArticleModel
from apps.analysis.time_weighted_news import NewsTimeWeightAnalyzer


class Command(BaseCommand):
    help = 'Debug time-weighted news analysis to understand why no news is found'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock',
            type=str,
            default='GPW',
            help='Stock symbol to debug'
        )

    def handle(self, *args, **options):
        """Debug time-weighted news analysis"""
        
        stock_symbol = options['stock']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🔍 Debugging Time-Weighted News Analysis for {stock_symbol}'
            )
        )
        self.stdout.write('=' * 70)
        
        try:
            stock = StockSymbol.objects.get(symbol=stock_symbol, is_active=True)
        except StockSymbol.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Stock {stock_symbol} not found')
            )
            return
        
        current_time = timezone.now()
        self.stdout.write(f'🕐 Current time: {current_time}')
        
        # Check all news articles for this stock
        all_news = NewsArticleModel.objects.filter(
            mentioned_stocks=stock
        ).order_by('-published_date')
        
        self.stdout.write(f'📰 Total news for {stock_symbol}: {all_news.count()}')
        
        # Show recent news with dates
        self.stdout.write('\\n📋 Recent news with dates:')
        for i, news in enumerate(all_news[:10], 1):
            age_hours = (current_time - news.published_date).total_seconds() / 3600
            self.stdout.write(
                f'{i}. {news.published_date} ({age_hours:.1f}h ago): '
                f'{news.title[:80]}...'
            )
            if hasattr(news, 'sentiment_score') and news.sentiment_score is not None:
                self.stdout.write(f'   📊 Sentiment: {news.sentiment_score:+.3f}')
        
        # Test different lookback periods
        self.stdout.write('\\n⏰ Testing different lookback periods:')
        
        for lookback_hours in [1, 4, 24, 48, 168]:  # 1h, 4h, 1d, 2d, 1w
            start_time = current_time - timedelta(hours=lookback_hours)
            
            news_in_period = NewsArticleModel.objects.filter(
                mentioned_stocks=stock,
                published_date__gte=start_time,
                published_date__lte=current_time,
                sentiment_score__isnull=False
            ).count()
            
            self.stdout.write(f'  • Last {lookback_hours}h: {news_in_period} articles')
        
        # Initialize analyzer and test
        self.stdout.write('\\n🔍 Testing NewsTimeWeightAnalyzer:')
        analyzer = NewsTimeWeightAnalyzer()
        
        # Test with different lookback periods
        for lookback_hours in [24, 48, 168]:
            sentiment_data = analyzer.calculate_weighted_sentiment(
                stock, current_time, lookback_hours
            )
            
            self.stdout.write(f'\\n📊 Lookback {lookback_hours}h results:')
            self.stdout.write(f'  • News count: {sentiment_data["news_count"]}')
            self.stdout.write(f'  • Confidence: {sentiment_data["confidence"]:.3f}')
            self.stdout.write(f'  • Weighted sentiment: {sentiment_data["weighted_sentiment_score"]:+.3f}')
            self.stdout.write(f'  • Recent news (4h): {sentiment_data["recent_news_count"]}')
            
            if sentiment_data["news_count"] > 0:
                self.stdout.write(f'  • Total weight: {sentiment_data["total_weight"]:.3f}')
                self.stdout.write(f'  • Breaking news: {sentiment_data["breaking_news_impact"]:.3f}')
                self.stdout.write(f'  • Momentum: {sentiment_data["sentiment_momentum"]:+.3f}')
        
        # Test intraday signal
        self.stdout.write('\\n🚦 Testing intraday sentiment signal:')
        signal_data = analyzer.get_intraday_sentiment_signal(stock, current_time)
        
        self.stdout.write(f'📊 Signal: {signal_data["signal"]}')
        self.stdout.write(f'📊 Signal strength: {signal_data["signal_strength"]:.3f}')
        
        # Show the raw query used by the analyzer
        self.stdout.write('\\n🔍 Testing raw news query:')
        start_time = current_time - timedelta(hours=24)
        
        raw_articles = NewsArticleModel.objects.filter(
            mentioned_stocks=stock,
            published_date__gte=start_time,
            published_date__lte=current_time,
            sentiment_score__isnull=False
        )
        
        self.stdout.write(f'📰 Raw query found: {raw_articles.count()} articles')
        for article in raw_articles[:5]:
            time_diff = (current_time - article.published_date).total_seconds() / 3600
            self.stdout.write(
                f'  • {article.published_date} ({time_diff:.1f}h ago): '
                f'Sentiment {article.sentiment_score:+.3f}'
            )
