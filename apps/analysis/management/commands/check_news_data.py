"""
Management command to check news data and stock associations
"""

from django.core.management.base import BaseCommand
from apps.news.models import NewsArticleModel
from apps.core.models import StockSymbol


class Command(BaseCommand):
    help = 'Check news data and stock associations'

    def handle(self, *args, **options):
        """Check news data status"""
        
        self.stdout.write(self.style.SUCCESS('📰 NEWS DATA STATUS'))
        self.stdout.write('=' * 50)
        
        # Count totals
        total_news = NewsArticleModel.objects.count()
        total_stocks = StockSymbol.objects.count()
        news_with_stocks = NewsArticleModel.objects.filter(mentioned_stocks__isnull=False).count()
        
        self.stdout.write(f'📊 Total news articles: {total_news}')
        self.stdout.write(f'📈 Total stock symbols: {total_stocks}')
        self.stdout.write(f'🔗 News with stock mentions: {news_with_stocks}')
        
        # Show recent news
        self.stdout.write('\\n📋 Recent News Articles:')
        recent_news = NewsArticleModel.objects.all()[:5]
        for i, news in enumerate(recent_news, 1):
            self.stdout.write(f'{i}. {news.title[:80]}...')
            stocks = list(news.mentioned_stocks.values_list('symbol', flat=True))
            if stocks:
                self.stdout.write(f'   📈 Mentions: {", ".join(stocks)}')
            else:
                self.stdout.write('   📈 No stock mentions')
        
        # Check specific stocks
        self.stdout.write('\\n📊 Stock-specific News:')
        for symbol in ['GPW', 'JSW', 'PKN', 'PZU', 'CDR', 'LPP']:
            try:
                stock = StockSymbol.objects.get(symbol=symbol)
                news_count = NewsArticleModel.objects.filter(mentioned_stocks=stock).count()
                self.stdout.write(f'  • {symbol}: {news_count} articles')
            except StockSymbol.DoesNotExist:
                self.stdout.write(f'  • {symbol}: stock not found')
        
        # Check for sentiment analysis
        self.stdout.write('\\n🔍 Sentiment Analysis Status:')
        analyzed_news = NewsArticleModel.objects.filter(
            sentiment_score__isnull=False
        ).count()
        self.stdout.write(f'📊 Analyzed articles: {analyzed_news}')
        
        if analyzed_news > 0:
            # Show sentiment distribution
            positive = NewsArticleModel.objects.filter(sentiment_score__gt=0.1).count()
            negative = NewsArticleModel.objects.filter(sentiment_score__lt=-0.1).count()
            neutral = NewsArticleModel.objects.filter(
                sentiment_score__gte=-0.1, 
                sentiment_score__lte=0.1
            ).count()
            
            self.stdout.write(f'  • Positive sentiment: {positive}')
            self.stdout.write(f'  • Negative sentiment: {negative}')
            self.stdout.write(f'  • Neutral sentiment: {neutral}')
