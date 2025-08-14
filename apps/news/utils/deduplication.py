"""
News deduplication utilities
"""

import hashlib
import difflib
from typing import Optional, Tuple
from django.db.models import Q
from apps.news.models import NewsArticleModel


class NewsDeduplicator:
    """Enhanced news deduplication with content similarity checking"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize deduplicator
        
        Args:
            similarity_threshold: Threshold for content similarity (0.0 - 1.0)
        """
        self.similarity_threshold = similarity_threshold
    
    def generate_content_hash(self, title: str, content: str) -> str:
        """Generate hash from title and content for fast duplicate detection"""
        combined_text = f"{title.strip().lower()}{content.strip().lower()}"
        # Remove whitespace and normalize
        normalized = ''.join(combined_text.split())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using difflib"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        text1_norm = ' '.join(text1.lower().split())
        text2_norm = ' '.join(text2.lower().split())
        
        # Calculate similarity
        similarity = difflib.SequenceMatcher(None, text1_norm, text2_norm).ratio()
        return similarity
    
    def find_duplicate_by_url(self, url: str) -> Optional[NewsArticleModel]:
        """Find duplicate by exact URL match"""
        try:
            return NewsArticleModel.objects.get(url=url)
        except NewsArticleModel.DoesNotExist:
            return None
    
    def find_duplicate_by_content(self, title: str, content: str, 
                                 source_id: Optional[int] = None) -> Optional[Tuple[NewsArticleModel, float]]:
        """
        Find duplicate by content similarity
        
        Returns:
            Tuple of (duplicate_article, similarity_score) or None
        """
        # Search within same source first, then expand
        query = Q()
        if source_id:
            query = Q(source_id=source_id)
        
        # Get recent articles for comparison (last 30 days for performance)
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        
        candidates = NewsArticleModel.objects.filter(
            query,
            published_date__gte=cutoff_date
        ).only('title', 'content', 'id', 'url')
        
        best_match = None
        best_similarity = 0.0
        
        # Compare with each candidate
        for candidate in candidates:
            # Compare titles first (faster)
            title_similarity = self.calculate_similarity(title, candidate.title)
            
            if title_similarity > 0.7:  # Pre-filter by title similarity
                # Full content comparison
                content_similarity = self.calculate_similarity(content, candidate.content)
                combined_similarity = (title_similarity * 0.3 + content_similarity * 0.7)
                
                if combined_similarity > best_similarity and combined_similarity >= self.similarity_threshold:
                    best_match = candidate
                    best_similarity = combined_similarity
        
        return (best_match, best_similarity) if best_match else None
    
    def is_duplicate(self, url: str, title: str, content: str, 
                    source_id: Optional[int] = None) -> Tuple[bool, Optional[NewsArticleModel], str]:
        """
        Comprehensive duplicate detection
        
        Returns:
            Tuple of (is_duplicate, existing_article, detection_method)
        """
        # 1. Check URL first (fastest)
        url_duplicate = self.find_duplicate_by_url(url)
        if url_duplicate:
            return True, url_duplicate, "url_exact_match"
        
        # 2. Check content similarity
        content_result = self.find_duplicate_by_content(title, content, source_id)
        if content_result:
            duplicate_article, similarity = content_result
            return True, duplicate_article, f"content_similarity_{similarity:.3f}"
        
        return False, None, "no_duplicate"
    
    def get_deduplication_stats(self) -> dict:
        """Get statistics about duplicate detection"""
        total_articles = NewsArticleModel.objects.count()
        
        # Count articles by source to detect potential duplicate patterns
        from django.db.models import Count
        source_stats = NewsArticleModel.objects.values('source__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'total_articles': total_articles,
            'articles_by_source': list(source_stats),
            'potential_efficiency': f"{(1 - len(source_stats)/max(total_articles, 1))*100:.1f}%" if total_articles > 0 else "0%"
        }


# Global instance
news_deduplicator = NewsDeduplicator()
