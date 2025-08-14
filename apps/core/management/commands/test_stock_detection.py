"""
Django management command for testing stock symbol detection
"""

from django.core.management.base import BaseCommand
from apps.core.utils.stock_detection import stock_symbol_detector
from apps.news.models import NewsArticleModel
from django.db.models import Q


class Command(BaseCommand):
    help = 'Test enhanced stock symbol detection on news articles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--article-id',
            type=int,
            help='Test specific article by ID'
        )
        parser.add_argument(
            '--sample-size',
            type=int,
            default=10,
            help='Number of random articles to test (default: 10)'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.7,
            help='Confidence threshold for detection (default: 0.7)'
        )
        parser.add_argument(
            '--text',
            type=str,
            help='Test detection on custom text'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== Stock Symbol Detection Test ===\n')
        )
        
        if options['text']:
            self.test_custom_text(options['text'], options['threshold'])
        elif options['article_id']:
            self.test_specific_article(options['article_id'], options['threshold'])
        else:
            self.test_sample_articles(options['sample_size'], options['threshold'])
    
    def test_custom_text(self, text: str, threshold: float):
        """Test detection on custom text"""
        self.stdout.write(f"Testing custom text with threshold {threshold}:")
        self.stdout.write(f"Text: {text}\n")
        
        # Test with confidence scores
        symbols_with_confidence = stock_symbol_detector.extract_stock_symbols(text, threshold)
        
        if symbols_with_confidence:
            self.stdout.write("📈 Detected symbols with confidence:")
            for symbol, confidence in sorted(symbols_with_confidence.items(), 
                                           key=lambda x: x[1], reverse=True):
                self.stdout.write(f"   • {symbol}: {confidence:.3f}")
        else:
            self.stdout.write("❌ No symbols detected")
    
    def test_specific_article(self, article_id: int, threshold: float):
        """Test detection on specific article"""
        try:
            article = NewsArticleModel.objects.get(id=article_id)
        except NewsArticleModel.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Article {article_id} not found')
            )
            return
        
        self.stdout.write(f"Testing article {article_id}:")
        self.stdout.write(f"Title: {article.title[:60]}...")
        self.stdout.write("")
        
        # Test detection
        text = f"{article.title} {article.content}"
        symbols_with_confidence = stock_symbol_detector.extract_stock_symbols(text, threshold)
        
        # Show current stock associations
        current_stocks = list(article.mentioned_stocks.values_list('symbol', flat=True))
        
        self.stdout.write(f"Current associations: {current_stocks}")
        
        if symbols_with_confidence:
            self.stdout.write("📈 Enhanced detection results:")
            for symbol, confidence in sorted(symbols_with_confidence.items(), 
                                           key=lambda x: x[1], reverse=True):
                status = "✅ (already associated)" if symbol in current_stocks else "🆕 (new detection)"
                self.stdout.write(f"   • {symbol}: {confidence:.3f} {status}")
        else:
            self.stdout.write("❌ No symbols detected")
    
    def test_sample_articles(self, sample_size: int, threshold: float):
        """Test detection on sample articles"""
        # Get articles with existing stock associations
        articles_with_stocks = NewsArticleModel.objects.filter(
            mentioned_stocks__isnull=False
        ).distinct()[:sample_size // 2]
        
        # Get articles without stock associations
        articles_without_stocks = NewsArticleModel.objects.filter(
            mentioned_stocks__isnull=True
        )[:sample_size // 2]
        
        all_articles = list(articles_with_stocks) + list(articles_without_stocks)
        
        self.stdout.write(f"Testing {len(all_articles)} articles with threshold {threshold}:")
        self.stdout.write("")
        
        total_improvements = 0
        total_new_detections = 0
        total_false_positives = 0
        
        for i, article in enumerate(all_articles, 1):
            current_stocks = set(article.mentioned_stocks.values_list('symbol', flat=True))
            
            # Test enhanced detection
            text = f"{article.title} {article.content}"
            detected_symbols = set(stock_symbol_detector.extract_stock_symbols(text, threshold).keys())
            
            # Compare results
            new_detections = detected_symbols - current_stocks
            potentially_missed = current_stocks - detected_symbols
            
            self.stdout.write(f"{i}. {article.title[:50]}...")
            
            if current_stocks:
                self.stdout.write(f"   Current: {sorted(current_stocks)}")
            
            if detected_symbols:
                self.stdout.write(f"   Detected: {sorted(detected_symbols)}")
            
            if new_detections:
                self.stdout.write(f"   🆕 New: {sorted(new_detections)}")
                total_new_detections += len(new_detections)
            
            if potentially_missed:
                self.stdout.write(f"   ⚠️  Potentially missed: {sorted(potentially_missed)}")
            
            if detected_symbols != current_stocks:
                total_improvements += 1
            
            self.stdout.write("")
        
        # Summary
        self.stdout.write("📊 Test Summary:")
        self.stdout.write(f"   • Articles tested: {len(all_articles)}")
        self.stdout.write(f"   • Articles with changes: {total_improvements}")
        self.stdout.write(f"   • New detections: {total_new_detections}")
        
        if len(all_articles) > 0:
            improvement_rate = (total_improvements / len(all_articles)) * 100
            self.stdout.write(f"   • Improvement rate: {improvement_rate:.1f}%")
