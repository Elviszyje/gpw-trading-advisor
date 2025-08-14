"""
Management command to perform sentiment analysis on news articles
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.news.models import NewsArticleModel
import random
import time


class Command(BaseCommand):
    help = 'Perform sentiment analysis on news articles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Number of articles to analyze (default: 50)'
        )
        parser.add_argument(
            '--stock-only',
            action='store_true',
            help='Only analyze articles that mention stocks'
        )

    def handle(self, *args, **options):
        """Analyze sentiment for news articles"""
        
        limit = options['limit']
        stock_only = options['stock_only']
        
        self.stdout.write(self.style.SUCCESS('🔍 NEWS SENTIMENT ANALYSIS'))
        self.stdout.write('=' * 50)
        
        # Get unanalyzed articles
        articles_query = NewsArticleModel.objects.filter(
            sentiment_score__isnull=True
        )
        
        if stock_only:
            articles_query = articles_query.filter(mentioned_stocks__isnull=False)
            self.stdout.write(f'📊 Filtering to articles with stock mentions')
        
        articles = articles_query[:limit]
        total_count = articles.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('⚠️  No unanalyzed articles found'))
            return
        
        self.stdout.write(f'📰 Found {total_count} articles to analyze')
        
        # Use mock sentiment analysis for testing
        self.stdout.write(self.style.WARNING('🔄 Using mock sentiment analysis for testing'))
        self._mock_sentiment_analysis(articles)
    
    def _mock_sentiment_analysis(self, articles):
        """Mock sentiment analysis for testing when LLM is not available"""
        
        self.stdout.write('🎭 Running mock sentiment analysis...')
        
        analyzed_count = 0
        
        for i, article in enumerate(articles, 1):
            self.stdout.write(f'\\n📰 [{i}/{len(articles)}] {article.title[:60]}...')
            
            try:
                # Generate mock sentiment based on keywords
                content_lower = f'{article.title} {article.content}'.lower()
                
                # Simple keyword-based sentiment
                positive_words = ['wzrost', 'zysk', 'sukces', 'dobra', 'pozytyw', 'korzyść', 'rekord']
                negative_words = ['spadek', 'strata', 'kryzys', 'problem', 'ryzyko', 'negatyw', 'utrata']
                
                positive_score = sum(1 for word in positive_words if word in content_lower)
                negative_score = sum(1 for word in negative_words if word in content_lower)
                
                # Calculate sentiment (-1.0 to 1.0)
                if positive_score > negative_score:
                    sentiment_score = min(1.0, 0.2 + (positive_score - negative_score) * 0.1)
                elif negative_score > positive_score:
                    sentiment_score = max(-1.0, -0.2 - (negative_score - positive_score) * 0.1)
                else:
                    sentiment_score = random.uniform(-0.1, 0.1)  # Neutral with small randomness
                
                # Determine impact based on stock mentions and sentiment strength
                stocks_mentioned = article.mentioned_stocks.count()
                impact_score = min(1.0, abs(sentiment_score) * (1 + stocks_mentioned * 0.2))
                
                if impact_score > 0.7:
                    market_impact = 'high'
                elif impact_score > 0.4:
                    market_impact = 'medium'
                else:
                    market_impact = 'low'
                
                # Update article
                with transaction.atomic():
                    article.sentiment_score = sentiment_score
                    article.market_impact = market_impact
                    article.impact_score = impact_score
                    article.is_analyzed = True
                    article.save()
                
                analyzed_count += 1
                
                # Display result
                self.stdout.write(f'  ✅ Sentiment: {sentiment_score:+.3f} | Impact: {market_impact} | Score: {impact_score:.3f}')
                
            except Exception as e:
                self.stdout.write(f'  ❌ Failed: {e}')
                continue
        
        # Summary
        self.stdout.write('\\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('📊 MOCK ANALYSIS SUMMARY'))
        self.stdout.write(f'✅ Analyzed: {analyzed_count}')
        self.stdout.write(f'📊 Success rate: {(analyzed_count / len(articles) * 100):.1f}%')
