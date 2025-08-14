"""
Advanced Analytics Service for GPW2 Trading Intelligence Platform
Provides comprehensive market analytics, sentiment trends, and performance metrics
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from apps.news.models import NewsArticleModel
from apps.core.models import StockSymbol, Industry, ScrapingExecution, NewsClassification

logger = logging.getLogger(__name__)


class AdvancedAnalyticsService:
    """Comprehensive analytics service for trading intelligence"""
    
    def __init__(self):
        self.default_period_days = 30
    
    def get_market_overview(self, days: Optional[int] = None) -> Dict:
        """Get comprehensive market overview with key metrics"""
        days = days or self.default_period_days
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Total articles and analysis coverage
        total_articles = NewsArticleModel.objects.filter(
            published_date__gte=cutoff_date
        ).count()
        
        analyzed_articles = NewsArticleModel.objects.filter(
            published_date__gte=cutoff_date,
            ai_classification__isnull=False
        ).count()
        
        # Sentiment distribution
        sentiment_distribution = NewsClassification.objects.filter(
            article__published_date__gte=cutoff_date
        ).values('sentiment').annotate(count=Count('id'))
        
        # Market impact distribution
        impact_distribution = NewsClassification.objects.filter(
            article__published_date__gte=cutoff_date
        ).values('market_impact').annotate(count=Count('id'))
        
        # Most mentioned stocks
        top_stocks = StockSymbol.objects.filter(
            news_mentions__published_date__gte=cutoff_date
        ).annotate(
            mention_count=Count('news_mentions', distinct=True)
        ).order_by('-mention_count')[:10]
        
        # Analysis coverage rate
        coverage_rate = (analyzed_articles / total_articles * 100) if total_articles > 0 else 0
        
        return {
            'period_days': days,
            'total_articles': total_articles,
            'analyzed_articles': analyzed_articles,
            'coverage_rate': round(coverage_rate, 1),
            'sentiment_distribution': list(sentiment_distribution),
            'impact_distribution': list(impact_distribution),
            'top_mentioned_stocks': [
                {
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'mentions': stock.mention_count
                }
                for stock in top_stocks
            ]
        }
    
    def get_sentiment_trends(self, days: Optional[int] = None, granularity: str = 'daily') -> Dict:
        """Get sentiment trends over time"""
        days = days or self.default_period_days
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Determine date truncation based on granularity
        date_trunc = 'day' if granularity == 'daily' else 'hour'
        
        # Get sentiment trends over time
        sentiment_trends = NewsClassification.objects.filter(
            article__published_date__gte=cutoff_date,
            sentiment__in=['positive', 'negative', 'neutral', 'very_positive', 'very_negative']
        ).extra(
            select={'date': f"DATE_TRUNC('{date_trunc}', created_at)"}
        ).values('date', 'sentiment').annotate(count=Count('id')).order_by('date')
        
        # Get average sentiment score trends
        sentiment_score_trends = NewsClassification.objects.filter(
            article__published_date__gte=cutoff_date,
            sentiment_score__isnull=False
        ).extra(
            select={'date': f"DATE_TRUNC('{date_trunc}', created_at)"}
        ).values('date').annotate(
            avg_sentiment=Avg('sentiment_score'),
            article_count=Count('id')
        ).order_by('date')
        
        return {
            'granularity': granularity,
            'period_days': days,
            'sentiment_counts': list(sentiment_trends),
            'sentiment_scores': list(sentiment_score_trends)
        }
    
    def get_stock_performance_analysis(self, symbol: Optional[str] = None, days: Optional[int] = None) -> Dict:
        """Get detailed stock performance analysis based on news sentiment"""
        days = days or self.default_period_days
        cutoff_date = timezone.now() - timedelta(days=days)
        
        if symbol:
            # Analysis for specific stock
            try:
                stock = StockSymbol.objects.get(symbol=symbol.upper())
            except StockSymbol.DoesNotExist:
                return {'error': f'Stock symbol {symbol} not found'}
            
            # Get news articles mentioning this stock
            articles = NewsArticleModel.objects.filter(
                published_date__gte=cutoff_date,
                mentioned_stocks=stock
            ).select_related('ai_classification')
            
            # Sentiment analysis for this stock
            classifications = NewsClassification.objects.filter(
                article__mentioned_stocks=stock,
                article__published_date__gte=cutoff_date
            )
            
            sentiment_stats = classifications.aggregate(
                avg_sentiment=Avg('sentiment_score'),
                avg_confidence=Avg('confidence_score'),
                total_articles=Count('id')
            )
            
            # Sentiment distribution
            sentiment_distribution = classifications.values('sentiment').annotate(
                count=Count('id')
            )
            
            # Recent news timeline
            recent_news = articles.filter(
                ai_classification__isnull=False
            ).order_by('-published_date')[:10]
            
            return {
                'stock': {
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': stock.sector
                },
                'period_days': days,
                'sentiment_stats': sentiment_stats,
                'sentiment_distribution': list(sentiment_distribution),
                'recent_news': [
                    {
                        'title': article.title,
                        'published_date': article.published_date,
                        'sentiment': article.ai_classification.sentiment if hasattr(article, 'ai_classification') else None,
                        'sentiment_score': article.ai_classification.sentiment_score if hasattr(article, 'ai_classification') else None,
                        'url': article.url
                    }
                    for article in recent_news
                ]
            }
        else:
            # Overall stock market sentiment analysis
            stock_performances = []
            
            # Get top mentioned stocks
            top_stocks = StockSymbol.objects.filter(
                news_mentions__published_date__gte=cutoff_date
            ).annotate(
                mention_count=Count('news_mentions', distinct=True)
            ).filter(mention_count__gte=3).order_by('-mention_count')[:20]
            
            for stock in top_stocks:
                classifications = NewsClassification.objects.filter(
                    article__mentioned_stocks=stock,
                    article__published_date__gte=cutoff_date
                )
                
                if classifications.exists():
                    stats = classifications.aggregate(
                        avg_sentiment=Avg('sentiment_score'),
                        avg_confidence=Avg('confidence_score'),
                        total_mentions=Count('id')
                    )
                    
                    stock_performances.append({
                        'symbol': stock.symbol,
                        'name': stock.name,
                        'mentions': stock.mention_count,
                        'avg_sentiment': round(stats['avg_sentiment'] or 0, 3),
                        'avg_confidence': round(stats['avg_confidence'] or 0, 3),
                        'total_analyzed': stats['total_mentions']
                    })
            
            # Sort by sentiment score (most positive first)
            stock_performances.sort(key=lambda x: x['avg_sentiment'], reverse=True)
            
            return {
                'period_days': days,
                'stock_count': len(stock_performances),
                'stock_performances': stock_performances
            }
    
    def get_industry_analysis(self, days: Optional[int] = None) -> Dict:
        """Get industry-wide sentiment and activity analysis"""
        days = days or self.default_period_days
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get industry performance based on stock mentions
        industry_stats = []
        
        industries = Industry.objects.all()
        
        for industry in industries:
            # Get stocks in this industry
            industry_stocks = StockSymbol.objects.filter(
                industries=industry
            )
            
            if industry_stocks.exists():
                # Get news articles mentioning stocks from this industry
                industry_articles = NewsClassification.objects.filter(
                    article__mentioned_stocks__in=industry_stocks,
                    article__published_date__gte=cutoff_date
                ).distinct()
                
                if industry_articles.exists():
                    stats = industry_articles.aggregate(
                        avg_sentiment=Avg('sentiment_score'),
                        article_count=Count('id')
                    )
                    
                    # Get sentiment distribution
                    sentiment_dist = industry_articles.values('sentiment').annotate(
                        count=Count('id')
                    )
                    
                    industry_stats.append({
                        'industry': industry.name,
                        'code': industry.code,
                        'article_count': stats['article_count'],
                        'avg_sentiment': round(stats['avg_sentiment'] or 0, 3),
                        'sentiment_distribution': list(sentiment_dist),
                        'stock_count': industry_stocks.count()
                    })
        
        # Sort by article count (most active industries first)
        industry_stats.sort(key=lambda x: x['article_count'], reverse=True)
        
        return {
            'period_days': days,
            'industries_analyzed': len(industry_stats),
            'industry_performance': industry_stats
        }
    
    def get_system_health_metrics(self) -> Dict:
        """Get comprehensive system health and performance metrics"""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        # Scraping performance
        recent_executions = ScrapingExecution.objects.filter(
            started_at__gte=last_24h
        )
        
        scraping_stats = recent_executions.aggregate(
            total_executions=Count('id'),
            successful_executions=Count('id', filter=Q(success=True)),
            total_items_processed=Count('items_processed'),
            total_items_created=Count('items_created')
        )
        
        success_rate = 0
        if scraping_stats['total_executions'] > 0:
            success_rate = (scraping_stats['successful_executions'] / 
                          scraping_stats['total_executions']) * 100
        
        # AI Analysis performance
        ai_stats_24h = NewsClassification.objects.filter(
            created_at__gte=last_24h
        ).count()
        
        ai_stats_7d = NewsClassification.objects.filter(
            created_at__gte=last_7d
        ).count()
        
        # Data quality metrics
        total_articles = NewsArticleModel.objects.count()
        analyzed_articles = NewsArticleModel.objects.filter(
            ai_classification__isnull=False
        ).count()
        
        analysis_coverage = (analyzed_articles / total_articles * 100) if total_articles > 0 else 0
        
        # Recent errors
        recent_errors = ScrapingExecution.objects.filter(
            started_at__gte=last_24h,
            success=False
        ).values('error_message', 'schedule__name').order_by('-started_at')[:5]
        
        return {
            'timestamp': now.isoformat(),
            'scraping_performance': {
                'last_24h_executions': scraping_stats['total_executions'],
                'success_rate': round(success_rate, 1),
                'items_processed': scraping_stats['total_items_processed'],
                'items_created': scraping_stats['total_items_created']
            },
            'ai_analysis_performance': {
                'analyses_last_24h': ai_stats_24h,
                'analyses_last_7d': ai_stats_7d,
                'analysis_coverage': round(analysis_coverage, 1)
            },
            'data_quality': {
                'total_articles': total_articles,
                'analyzed_articles': analyzed_articles,
                'coverage_percentage': round(analysis_coverage, 1)
            },
            'recent_errors': list(recent_errors)
        }
    
    def get_alert_candidates(self, sentiment_threshold: float = 0.8, 
                           impact_threshold: float = 0.7) -> Dict:
        """Get articles that could trigger alerts based on sentiment and market impact"""
        cutoff_date = timezone.now() - timedelta(hours=24)
        
        # High-impact positive news (using market_impact field)
        positive_alerts = NewsClassification.objects.filter(
            article__published_date__gte=cutoff_date,
            sentiment_score__gte=sentiment_threshold,
            market_impact__in=['high', 'very_high'],
            sentiment__in=['positive', 'very_positive']
        ).select_related('article').order_by('-sentiment_score')[:10]
        
        # High-impact negative news
        negative_alerts = NewsClassification.objects.filter(
            article__published_date__gte=cutoff_date,
            sentiment_score__lte=-sentiment_threshold,
            market_impact__in=['high', 'very_high'],
            sentiment__in=['negative', 'very_negative']
        ).select_related('article').order_by('sentiment_score')[:10]
        
        # Format alert data
        def format_alert(classification):
            # Convert market_impact to numeric for display
            impact_map = {
                'very_high': 0.9,
                'high': 0.8,
                'medium': 0.6,
                'low': 0.4,
                'minimal': 0.2
            }
            impact_score = impact_map.get(classification.market_impact, 0.5)
            
            return {
                'title': classification.article.title,
                'sentiment': classification.sentiment,
                'sentiment_score': classification.sentiment_score,
                'impact_score': impact_score,
                'confidence': classification.confidence_score,
                'published_date': classification.article.published_date,
                'mentioned_stocks': list(
                    classification.article.mentioned_stocks.values_list('symbol', flat=True)
                ),
                'url': classification.article.url
            }
        
        return {
            'threshold_sentiment': sentiment_threshold,
            'threshold_impact': impact_threshold,
            'positive_alerts': [format_alert(alert) for alert in positive_alerts],
            'negative_alerts': [format_alert(alert) for alert in negative_alerts],
            'alert_count': len(positive_alerts) + len(negative_alerts)
        }


# Global analytics service instance
analytics_service = AdvancedAnalyticsService()
