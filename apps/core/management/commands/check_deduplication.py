"""
Django management command for checking news deduplication statistics
"""

from django.core.management.base import BaseCommand
from apps.news.utils.deduplication import news_deduplicator
from apps.news.models import NewsArticleModel
from django.db.models import Count, Q
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Check news deduplication statistics and effectiveness'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-similarity',
            action='store_true',
            help='Test content similarity detection on recent articles'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze (default: 7)'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.85,
            help='Similarity threshold for testing (default: 0.85)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('=== News Deduplication Analysis ===\n')
        )
        
        # Basic statistics
        self.show_basic_stats()
        
        if options['test_similarity']:
            self.test_similarity_detection(
                days=options['days'],
                threshold=options['threshold']
            )
    
    def show_basic_stats(self):
        """Show basic deduplication statistics"""
        stats = news_deduplicator.get_deduplication_stats()
        
        self.stdout.write("📊 Basic Statistics:")
        self.stdout.write(f"   Total articles: {stats['total_articles']}")
        self.stdout.write(f"   Deduplication efficiency: {stats['potential_efficiency']}")
        self.stdout.write("")
        
        self.stdout.write("📈 Articles by Source:")
        for source_stat in stats['articles_by_source'][:10]:  # Top 10 sources
            self.stdout.write(f"   • {source_stat['source__name']}: {source_stat['count']} articles")
        
        self.stdout.write("")
        
        # URL uniqueness check
        total_articles = NewsArticleModel.objects.count()
        unique_urls = NewsArticleModel.objects.values('url').distinct().count()
        
        if total_articles > 0:
            url_uniqueness = (unique_urls / total_articles) * 100
            self.stdout.write(f"🔗 URL Uniqueness: {url_uniqueness:.1f}% ({unique_urls}/{total_articles})")
        
        # Potential duplicates by title similarity
        self.find_potential_title_duplicates()
    
    def find_potential_title_duplicates(self):
        """Find articles with very similar titles"""
        self.stdout.write("\n🔍 Potential Title Duplicates:")
        
        # Get recent articles
        recent_articles = NewsArticleModel.objects.filter(
            published_date__gte=datetime.now() - timedelta(days=7)
        ).values('id', 'title', 'url', 'source__name')
        
        potential_duplicates = []
        checked_pairs = set()
        
        for article1 in recent_articles:
            for article2 in recent_articles:
                if article1['id'] != article2['id']:
                    pair_key = tuple(sorted([article1['id'], article2['id']]))
                    if pair_key not in checked_pairs:
                        checked_pairs.add(pair_key)
                        
                        similarity = news_deduplicator.calculate_similarity(
                            article1['title'], article2['title']
                        )
                        
                        if similarity > 0.8:  # High title similarity
                            potential_duplicates.append({
                                'article1': article1,
                                'article2': article2,
                                'similarity': similarity
                            })
        
        if potential_duplicates:
            self.stdout.write(f"   Found {len(potential_duplicates)} potential duplicates:")
            for i, dup in enumerate(potential_duplicates[:5]):  # Show top 5
                a1, a2 = dup['article1'], dup['article2']
                self.stdout.write(
                    f"   {i+1}. Similarity: {dup['similarity']:.3f}\n"
                    f"      • {a1['title'][:60]}... ({a1['source__name']})\n"
                    f"      • {a2['title'][:60]}... ({a2['source__name']})"
                )
        else:
            self.stdout.write("   ✅ No obvious title duplicates found")
    
    def test_similarity_detection(self, days: int, threshold: float):
        """Test content similarity detection"""
        self.stdout.write(f"\n🧪 Testing Similarity Detection (last {days} days, threshold: {threshold}):")
        
        # Update deduplicator threshold
        news_deduplicator.similarity_threshold = threshold
        
        # Get recent articles for testing
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_articles = NewsArticleModel.objects.filter(
            published_date__gte=cutoff_date
        ).select_related('source')[:50]  # Limit for performance
        
        self.stdout.write(f"   Testing on {len(recent_articles)} recent articles...")
        
        detected_duplicates = 0
        false_positives = 0
        
        for i, article in enumerate(recent_articles):
            # Test if this article would be detected as duplicate
            is_dup, existing_article, detection_method = news_deduplicator.is_duplicate(
                url=f"test_url_{i}",  # Use test URL to avoid URL-based detection
                title=article.title,
                content=article.content[:500],  # Limit content for performance
                source_id=article.source.pk
            )
            
            if is_dup and "content_similarity" in detection_method:
                detected_duplicates += 1
                if existing_article and existing_article.pk != article.pk:
                    similarity_score = float(detection_method.split('_')[-1])
                    self.stdout.write(
                        f"   🔍 Detected similarity ({similarity_score:.3f}):\n"
                        f"      Original: {article.title[:50]}...\n"
                        f"      Similar:  {existing_article.title[:50]}..."
                    )
                else:
                    false_positives += 1
        
        self.stdout.write(f"\n📊 Test Results:")
        self.stdout.write(f"   • Detected duplicates: {detected_duplicates}")
        self.stdout.write(f"   • Potential false positives: {false_positives}")
        
        if len(recent_articles) > 0:
            detection_rate = (detected_duplicates / len(recent_articles)) * 100
            self.stdout.write(f"   • Detection rate: {detection_rate:.1f}%")
