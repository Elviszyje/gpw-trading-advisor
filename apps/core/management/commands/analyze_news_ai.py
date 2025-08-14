"""
Django management command to analyze news articles with AI
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.news.models import NewsArticleModel
from apps.core.models import NewsClassification, LLMProvider
from apps.core.llm_service import LLMService, analyze_article_with_ai
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Analyze news articles using AI for sentiment and industry classification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            choices=['openai', 'ollama'],
            help='Specify LLM provider to use (openai or ollama)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Maximum number of articles to analyze (default: 5)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-analyze articles that were already processed'
        )
        parser.add_argument(
            '--article-id',
            type=int,
            help='Analyze specific article by ID'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== AI News Analysis Started ===')
        )

        # Initialize LLM service
        service = LLMService()
        
        # Get provider
        provider = None
        if options['provider']:
            try:
                provider = LLMProvider.objects.get(
                    provider_type=options['provider'],
                    is_active=True
                )
                if not service.check_provider_availability(provider):
                    self.stdout.write(
                        self.style.ERROR(f'Provider {provider.name} is not available')
                    )
                    return
            except LLMProvider.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Provider {options["provider"]} not found')
                )
                return
        else:
            provider = service.get_available_provider()
            if not provider:
                self.stdout.write(
                    self.style.ERROR('No available LLM providers found')
                )
                return

        self.stdout.write(f'Using provider: {provider.name}')

        # Get articles to analyze
        if options['article_id']:
            try:
                articles = [NewsArticleModel.objects.get(id=options['article_id'])]
            except NewsArticleModel.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Article {options["article_id"]} not found')
                )
                return
        else:
            # Get articles without analysis or force re-analysis
            if options['force']:
                articles = NewsArticleModel.objects.all()[:options['limit']]
            else:
                articles = NewsArticleModel.objects.filter(
                    ai_classification__isnull=True
                )[:options['limit']]

        if not articles:
            self.stdout.write(
                self.style.WARNING('No articles to analyze')
            )
            return

        self.stdout.write(f'Found {len(articles)} articles to analyze\n')

        # Analyze articles
        success_count = 0
        error_count = 0

        for i, article in enumerate(articles, 1):
            self.stdout.write(f'[{i}/{len(articles)}] Analyzing: {article.title[:60]}...')
            
            try:
                # Delete existing classification if force mode
                if options['force']:
                    try:
                        article.ai_classification.delete()
                    except NewsClassification.DoesNotExist:
                        pass

                # Analyze article
                classification = service.analyze_news_article(article, provider)
                
                if classification:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'   ✅ Sentiment: {classification.sentiment} '
                            f'({classification.sentiment_score:.2f}), '
                            f'Impact: {classification.market_impact}'
                        )
                    )
                    
                    if classification.detected_industries.exists():
                        industries = ', '.join([
                            ind.name for ind in classification.detected_industries.all()
                        ])
                        self.stdout.write(f'   📊 Industries: {industries}')
                    
                    if classification.mentioned_companies:
                        companies = ', '.join(classification.mentioned_companies[:3])
                        self.stdout.write(f'   🏢 Companies: {companies}')
                        
                    if article.mentioned_stocks.exists():
                        stocks = ', '.join([
                            stock.symbol for stock in article.mentioned_stocks.all()
                        ])
                        self.stdout.write(f'   📈 Stocks: {stocks}')
                        
                    self.stdout.write(
                        f'   ⏱️  Processing time: {classification.processing_time_ms}ms'
                    )
                    
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR('   ❌ Analysis failed')
                    )
                    error_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Error: {str(e)}')
                )
                error_count += 1
                
            self.stdout.write('')  # Empty line for readability

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Analysis Complete ===\n'
                f'Successfully analyzed: {success_count}\n'
                f'Errors: {error_count}\n'
                f'Provider used: {provider.name}\n'
                f'Total requests: {provider.requests_count}'
            )
        )

        # Show recent classifications
        if success_count > 0:
            self.stdout.write('\n=== Recent Classifications ===')
            recent = NewsClassification.objects.filter(
                llm_provider=provider
            ).order_by('-created_at')[:3]
            
            for classification in recent:
                self.stdout.write(
                    f'• {classification.article.title[:50]}...\n'
                    f'  Sentiment: {classification.sentiment} '
                    f'({classification.sentiment_score:.2f})\n'
                    f'  Summary: {classification.ai_summary[:100]}...\n'
                )
