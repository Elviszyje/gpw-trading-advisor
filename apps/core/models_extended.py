"""
Extended models for market classification and industry analysis
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Market(models.Model):
    """
    Stock market definitions (Main Market, NewConnect, Catalyst, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Market characteristics
    is_regulated = models.BooleanField(default=True)
    min_market_cap = models.BigIntegerField(null=True, blank=True, help_text="Minimum market cap in PLN")
    trading_hours_start = models.TimeField(null=True, blank=True)
    trading_hours_end = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_markets'
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.code})"


class Industry(models.Model):
    """
    Industry/sector classification for companies
    """
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Industry hierarchy
    parent_industry = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='sub_industries'
    )
    
    # Industry characteristics
    is_cyclical = models.BooleanField(default=False)
    volatility_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low Volatility'),
            ('medium', 'Medium Volatility'),
            ('high', 'High Volatility'),
        ],
        default='medium'
    )
    
    # Keywords for AI classification
    keywords = models.JSONField(default=list, blank=True, help_text="Keywords for automatic classification")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_industries'
        ordering = ['name']
        verbose_name_plural = 'Industries'
        
    def __str__(self):
        if self.parent_industry:
            return f"{self.parent_industry.name} > {self.name}"
        return self.name
        
    @property
    def full_path(self):
        """Get full industry path"""
        if self.parent_industry:
            return f"{self.parent_industry.full_path} > {self.name}"
        return self.name


class LLMProvider(models.Model):
    """
    Configuration for LLM providers (OpenAI, OLLAMA, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    provider_type = models.CharField(
        max_length=20,
        choices=[
            ('openai', 'OpenAI'),
            ('ollama', 'OLLAMA'),
            ('huggingface', 'HuggingFace'),
            ('anthropic', 'Anthropic'),
        ]
    )
    
    # Configuration
    api_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    model_name = models.CharField(max_length=100)
    
    # Performance settings
    max_tokens = models.IntegerField(default=1000)
    temperature = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=False)
    last_check = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    requests_count = models.IntegerField(default=0)
    total_tokens_used = models.BigIntegerField(default=0)
    last_request = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_llm_providers'
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.provider_type})"


class NewsClassification(models.Model):
    """
    AI-powered classification results for news articles
    """
    # Link to news article
    article = models.OneToOneField(
        'news.NewsArticleModel',
        on_delete=models.CASCADE,
        related_name='ai_classification'
    )
    
    # LLM provider used
    llm_provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.SET_NULL,
        null=True,
        related_name='classifications'
    )
    
    # AI Analysis Results
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('very_positive', 'Very Positive'),
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
            ('very_negative', 'Very Negative'),
        ],
        null=True,
        blank=True
    )
    sentiment_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)]
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Industry classification
    detected_industries = models.ManyToManyField(
        Industry,
        blank=True,
        related_name='news_classifications'
    )
    primary_industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_news_classifications'
    )
    
    # Market impact assessment
    market_impact = models.CharField(
        max_length=20,
        choices=[
            ('very_high', 'Very High Impact'),
            ('high', 'High Impact'),
            ('medium', 'Medium Impact'),
            ('low', 'Low Impact'),
            ('minimal', 'Minimal Impact'),
        ],
        null=True,
        blank=True
    )
    
    # AI-extracted entities
    mentioned_companies = models.JSONField(default=list, blank=True)
    mentioned_people = models.JSONField(default=list, blank=True)
    mentioned_locations = models.JSONField(default=list, blank=True)
    key_topics = models.JSONField(default=list, blank=True)
    
    # AI reasoning
    ai_summary = models.TextField(blank=True)
    ai_reasoning = models.TextField(blank=True)
    key_phrases = models.JSONField(default=list, blank=True)
    
    # Processing metadata
    processing_time_ms = models.IntegerField(null=True, blank=True)
    tokens_used = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_news_classifications'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Classification for: {self.article.title[:50]}..."
