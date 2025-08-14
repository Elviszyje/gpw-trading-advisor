"""
Management command to demonstrate time-weighted news analysis with simulated recent news
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction

from apps.core.models import StockSymbol
from apps.news.models import NewsArticleModel
from apps.analysis.time_weighted_news import NewsTimeWeightAnalyzer
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator


class Command(BaseCommand):
    help = 'Demonstrate time-weighted news analysis with simulated recent news'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock',
            type=str,
            default='GPW',
            help='Stock symbol to demonstrate'
        )
        parser.add_argument(
            '--restore',
            action='store_true',
            help='Restore original news dates after demo'
        )

    def handle(self, *args, **options):
        """Demonstrate time-weighted news analysis"""
        
        stock_symbol = options['stock']
        restore = options['restore']
        
        if restore:
            self._restore_original_dates()
            return
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🎭 Demonstrating Time-Weighted News Analysis for {stock_symbol}'
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
        
        # Get news articles for this stock
        news_articles = NewsArticleModel.objects.filter(
            mentioned_stocks=stock,
            sentiment_score__isnull=False
        ).order_by('-published_date')[:10]
        
        if not news_articles:
            self.stdout.write(
                self.style.ERROR(f'❌ No analyzed news articles found for {stock_symbol}')
            )
            return
        
        self.stdout.write(f'📰 Found {len(news_articles)} analyzed articles for {stock_symbol}')
        
        # Simulate recent news by adjusting publication dates
        current_time = timezone.now()
        original_dates = {}
        
        self.stdout.write('\\n🕐 Simulating recent news by adjusting publication dates...')
        
        simulated_times = [
            current_time - timedelta(minutes=10),   # Very recent
            current_time - timedelta(minutes=30),   # Recent
            current_time - timedelta(minutes=90),   # 1.5 hours ago
            current_time - timedelta(hours=3),      # 3 hours ago
            current_time - timedelta(hours=6),      # 6 hours ago
        ]
        
        with transaction.atomic():
            for i, article in enumerate(news_articles[:5]):
                original_dates[article.id] = article.published_date
                article.published_date = simulated_times[i]
                article.save()
                
                time_ago = (current_time - article.published_date).total_seconds() / 60
                self.stdout.write(
                    f'  📰 {article.title[:60]}... -> {time_ago:.0f} min ago'
                )
        
        # Test time-weighted analysis
        self.stdout.write('\\n🔍 Testing Time-Weighted News Analysis:')
        analyzer = NewsTimeWeightAnalyzer()
        
        # Test intraday signal
        signal_data = analyzer.get_intraday_sentiment_signal(stock, current_time)
        
        self.stdout.write(f'\\n🚦 Intraday Trading Signal:')
        self.stdout.write(f'  📊 Signal: {signal_data["signal"]}')
        self.stdout.write(f'  📊 Signal strength: {signal_data["signal_strength"]:.3f}')
        
        sentiment_data = signal_data['sentiment_data']
        self.stdout.write(f'\\n📈 Sentiment Analysis:')
        self.stdout.write(f'  📰 News count: {sentiment_data["news_count"]}')
        self.stdout.write(f'  📊 Confidence: {sentiment_data["confidence"]:.3f}')
        self.stdout.write(f'  📊 Weighted sentiment: {sentiment_data["weighted_sentiment_score"]:+.3f}')
        self.stdout.write(f'  📊 Recent news (4h): {sentiment_data["recent_news_count"]}')
        self.stdout.write(f'  📊 Breaking news impact: {sentiment_data["breaking_news_impact"]:.3f}')
        self.stdout.write(f'  📊 Sentiment momentum: {sentiment_data["sentiment_momentum"]:+.3f}')
        self.stdout.write(f'  📊 Total weight: {sentiment_data["total_weight"]:.3f}')
        
        # Test with different configurations
        self.stdout.write('\\n⚙️ Testing Different Configurations:')
        
        configs = ['intraday_aggressive', 'intraday_conservative', 'swing_trading']
        for config_name in configs:
            try:
                test_analyzer = NewsTimeWeightAnalyzer(config_name)
                test_signal = test_analyzer.get_intraday_sentiment_signal(stock, current_time)
                
                self.stdout.write(f'\\n  📊 {config_name}:')
                self.stdout.write(f'    Signal: {test_signal["signal"]} (strength: {test_signal["signal_strength"]:.3f})')
                self.stdout.write(f'    Confidence: {test_signal["sentiment_data"]["confidence"]:.3f}')
                
            except Exception as e:
                self.stdout.write(f'    ❌ Error: {e}')
        
        # Show impact of time weighting
        self.stdout.write('\\n⏰ Time Weighting Details:')
        for i, article in enumerate(news_articles[:5]):
            time_weight = analyzer.calculate_time_weight(article.published_date, current_time)
            timing_multiplier = analyzer.calculate_market_timing_multiplier(article.published_date)
            
            minutes_ago = (current_time - article.published_date).total_seconds() / 60
            self.stdout.write(
                f'  📰 Article {i+1} ({minutes_ago:.0f}min ago): '
                f'Time weight {time_weight:.3f} × Timing {timing_multiplier:.1f}x = '
                f'{time_weight * timing_multiplier:.3f}'
            )
            if hasattr(article, 'sentiment_score'):
                self.stdout.write(f'      Sentiment: {article.sentiment_score:+.3f}')
        
        # Compare with base trading signal
        self.stdout.write('\\n🔍 Integration with Base Trading Signals:')
        signal_generator = DailyTradingSignalGenerator()
        base_signal = signal_generator.generate_signals_for_stock(stock)
        
        self.stdout.write(f'📊 Base technical signal: {base_signal.get("signal", "N/A")}')
        self.stdout.write(f'📊 Base confidence: {base_signal.get("confidence", 0):.1f}%')
        self.stdout.write(f'📊 News would modify signal: {self._would_modify_signal(base_signal, signal_data)}')
        
        # Restore original dates
        self.stdout.write('\\n🔄 Restoring original publication dates...')
        with transaction.atomic():
            for article_id, original_date in original_dates.items():
                article = NewsArticleModel.objects.get(id=article_id)
                article.published_date = original_date
                article.save()
        
        self.stdout.write('\\n✅ Demonstration completed! Original dates restored.')
        self.stdout.write('\\n💡 Key Benefits of Time-Weighted News Analysis:')
        self.stdout.write('  • Recent news gets higher impact weights (40% for last 15min)')
        self.stdout.write('  • Breaking news gets 2x multiplier')
        self.stdout.write('  • Market hours news gets 1.5x multiplier')
        self.stdout.write('  • Sentiment momentum tracks changing market sentiment')
        self.stdout.write('  • Configurable for different trading styles (intraday/swing/position)')
    
    def _would_modify_signal(self, base_signal, news_analysis):
        """Determine if news analysis would modify the base signal"""
        sentiment_data = news_analysis['sentiment_data']
        
        if sentiment_data['confidence'] < 0.3:
            return False
        
        sentiment_score = abs(sentiment_data['weighted_sentiment_score'])
        if sentiment_score < 0.1:
            return False
        
        return True
    
    def _restore_original_dates(self):
        """Restore original publication dates (if needed)"""
        self.stdout.write('🔄 Note: Publication dates are automatically restored after each demo')
        return True
