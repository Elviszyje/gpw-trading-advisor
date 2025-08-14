"""
News Models - ONLY for news articles and ESPI reports
Calendar events are handled in apps/scrapers/
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()


class NewsSource(models.Model):
    """
    News source configuration for RSS feeds and news portals
    """
    name = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    type = models.CharField(max_length=20, choices=[
        ('rss', 'RSS Feed'),
        ('html', 'HTML Scraping'),
        ('api', 'API'),
    ])
    is_active = models.BooleanField(default=True)
    scraping_config = models.JSONField(default=dict, blank=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'news_sources'
    
    def __str__(self):
        return f"{self.name} ({self.type})"


class NewsArticleModel(models.Model):
    """
    News articles with sentiment analysis capability
    """
    IMPACT_CHOICES = [
        ('high', 'High Impact'),
        ('medium', 'Medium Impact'), 
        ('low', 'Low Impact'),
        ('unknown', 'Unknown Impact'),
    ]
    
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('neutral', 'Neutral'),
        ('unknown', 'Unknown'),
    ]
    
    title = models.CharField(max_length=500)
    content = models.TextField()
    url = models.URLField(unique=True, max_length=500)
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name='articles')
    
    # Stock associations
    mentioned_stocks = models.ManyToManyField('core.StockSymbol', blank=True, related_name='news_mentions')
    primary_stock = models.ForeignKey('core.StockSymbol', on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_news')
    
    # Analysis fields
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, default='unknown')
    sentiment_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)])
    market_impact = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='unknown')
    impact_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    # Keywords and tags
    keywords = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Metadata
    published_date = models.DateTimeField()
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analysis status
    is_analyzed = models.BooleanField(default=False)
    analysis_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'news_articles'
        ordering = ['-published_date']
        indexes = [
            models.Index(fields=['published_date']),
            models.Index(fields=['sentiment']),
            models.Index(fields=['market_impact']),
            models.Index(fields=['source']),
        ]
    
    def __str__(self):
        return f"{self.title[:50]}... ({self.source.name})"
