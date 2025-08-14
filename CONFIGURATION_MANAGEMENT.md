# 🎛️ Enhanced Trading Signals - Configuration Management

## 📋 **CONFIGURATION PROFILES**

### **PROFILE 1: Conservative (Low Risk)**
```python
CONSERVATIVE_CONFIG = {
    'news_sentiment_boost_threshold': 0.6,      # Wyższy próg dla boost
    'news_sentiment_penalty_threshold': -0.4,   # Niższy próg dla penalty
    'news_confidence_boost': 10.0,              # Mniejszy boost
    'news_confidence_penalty': 15.0,            # Mniejszy penalty
    'enable_signal_modification': False,        # Nie zmieniaj sygnałów BUY→HOLD
    'enable_confidence_adjustment': True,       # Tylko adjustuj confidence
    'source_weights': {
        'stooq': 1.0,           # Tylko zaufane źródła
        'strefainwestorow': 0.6, # Mniejsza waga dla portali
    }
}
```

### **PROFILE 2: Balanced (Default)**  
```python
BALANCED_CONFIG = {
    'news_sentiment_boost_threshold': 0.5,
    'news_sentiment_penalty_threshold': -0.5,
    'news_confidence_boost': 15.0,
    'news_confidence_penalty': 20.0,  
    'enable_signal_modification': True,
    'enable_confidence_adjustment': True,
    'source_weights': {
        'stooq': 1.0,
        'strefainwestorow': 0.8,
        'bankier': 0.8,
    }
}
```

### **PROFILE 3: Aggressive (High Sensitivity)**
```python
AGGRESSIVE_CONFIG = {
    'news_sentiment_boost_threshold': 0.3,      # Niski próg - reaguj szybciej
    'news_sentiment_penalty_threshold': -0.3,   # Niski próg - reaguj szybciej
    'news_confidence_boost': 25.0,              # Większy boost
    'news_confidence_penalty': 30.0,            # Większy penalty
    'enable_signal_modification': True,
    'enable_confidence_adjustment': True,
    'enable_hold_to_buy_conversion': True,      # Generuj BUY z HOLD
    'source_weights': {
        'stooq': 1.0,
        'strefainwestorow': 0.8,
        'bankier': 0.8,
        'social_media': 0.4,    # FUTURE - uwzględniaj social media
    }
}
```

## 🔧 **CONFIGURATION MODEL**

```python
# apps/analysis/models.py
class EnhancedSignalConfig(models.Model):
    """
    Configuration model for Enhanced Trading Signals.
    Allows easy parameter tuning without code changes.
    """
    
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # News analysis thresholds
    news_sentiment_boost_threshold = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.5,
        help_text="Sentiment above this triggers confidence boost"
    )
    news_sentiment_penalty_threshold = models.DecimalField(
        max_digits=3, decimal_places=2, default=-0.5,
        help_text="Sentiment below this triggers confidence penalty"  
    )
    high_impact_news_multiplier = models.DecimalField(
        max_digits=3, decimal_places=2, default=1.5,
        help_text="Multiplier for high-impact news effects"
    )
    
    # Confidence adjustments
    news_confidence_boost = models.DecimalField(
        max_digits=4, decimal_places=1, default=15.0,
        help_text="Confidence boost % for positive news"
    )
    news_confidence_penalty = models.DecimalField(
        max_digits=4, decimal_places=1, default=20.0,
        help_text="Confidence penalty % for negative news"
    )
    
    # Analysis parameters
    news_analysis_window_days = models.PositiveIntegerField(
        default=7,
        help_text="Days to look back for news analysis"
    )
    
    # Source weights (JSON)
    source_weights = models.JSONField(
        default=dict,
        help_text="Weight for each news source"
    )
    
    # Feature flags
    is_active = models.BooleanField(default=False)
    enable_signal_modification = models.BooleanField(
        default=True,
        help_text="Allow changing signal type (BUY→HOLD, etc.)"
    )
    enable_confidence_adjustment = models.BooleanField(
        default=True,
        help_text="Allow adjusting signal confidence"
    )
    enable_hold_to_buy_conversion = models.BooleanField(
        default=False,
        help_text="Convert HOLD to BUY on very positive news"
    )
    enable_buy_to_hold_conversion = models.BooleanField(
        default=True,
        help_text="Convert BUY to HOLD on very negative news"  
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    class Meta:
        db_table = 'enhanced_signal_configs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"
    
    @classmethod
    def get_active_config(cls):
        """Get currently active configuration."""
        return cls.objects.filter(is_active=True).first()
    
    def activate(self):
        """Activate this configuration (deactivate others)."""
        cls.objects.update(is_active=False)  # Deactivate all
        self.is_active = True
        self.save()
```

## 🎛️ **CONFIGURATION MANAGER**

```python
# apps/analysis/config_manager.py
from typing import Dict, Any
from apps.analysis.models import EnhancedSignalConfig

class ConfigurationManager:
    """
    Central configuration manager for Enhanced Trading Signals.
    Handles config loading, validation, and hot-reloading.
    """
    
    _instance = None
    _config_cache = None
    _cache_timestamp = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_active_config(self) -> Dict[str, Any]:
        """
        Get active configuration with caching.
        Cache expires after 5 minutes for hot-reloading.
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        # Check cache validity
        if (self._config_cache is None or 
            self._cache_timestamp is None or 
            now - self._cache_timestamp > timedelta(minutes=5)):
            
            # Reload config from database
            config = EnhancedSignalConfig.get_active_config()
            
            if config:
                self._config_cache = self._model_to_dict(config)
            else:
                # Fall back to default config
                self._config_cache = self._get_default_config()
            
            self._cache_timestamp = now
        
        return self._config_cache
    
    def _model_to_dict(self, config: EnhancedSignalConfig) -> Dict[str, Any]:
        """Convert model instance to configuration dictionary."""
        return {
            'name': config.name,
            'news_sentiment_boost_threshold': float(config.news_sentiment_boost_threshold),
            'news_sentiment_penalty_threshold': float(config.news_sentiment_penalty_threshold),
            'high_impact_news_multiplier': float(config.high_impact_news_multiplier),
            'news_confidence_boost': float(config.news_confidence_boost),
            'news_confidence_penalty': float(config.news_confidence_penalty),
            'news_analysis_window_days': config.news_analysis_window_days,
            'source_weights': config.source_weights,
            'enable_signal_modification': config.enable_signal_modification,
            'enable_confidence_adjustment': config.enable_confidence_adjustment,
            'enable_hold_to_buy_conversion': config.enable_hold_to_buy_conversion,
            'enable_buy_to_hold_conversion': config.enable_buy_to_hold_conversion,
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if no active config found."""
        return {
            'name': 'default_fallback',
            'news_sentiment_boost_threshold': 0.5,
            'news_sentiment_penalty_threshold': -0.5,
            'high_impact_news_multiplier': 1.5,
            'news_confidence_boost': 15.0,
            'news_confidence_penalty': 20.0,
            'news_analysis_window_days': 7,
            'source_weights': {
                'stooq': 1.0,
                'strefainwestorow': 0.8,
                'bankier': 0.8
            },
            'enable_signal_modification': True,
            'enable_confidence_adjustment': True,
            'enable_hold_to_buy_conversion': False,
            'enable_buy_to_hold_conversion': True,
        }
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration parameters.
        Returns list of validation errors.
        """
        errors = []
        
        # Threshold validation
        boost = config.get('news_sentiment_boost_threshold', 0)
        penalty = config.get('news_sentiment_penalty_threshold', 0)
        
        if boost <= 0 or boost > 1:
            errors.append("news_sentiment_boost_threshold must be between 0 and 1")
        if penalty >= 0 or penalty < -1:
            errors.append("news_sentiment_penalty_threshold must be between -1 and 0")
        if boost <= abs(penalty):
            errors.append("boost_threshold must be higher than abs(penalty_threshold)")
        
        # Confidence validation
        conf_boost = config.get('news_confidence_boost', 0)
        conf_penalty = config.get('news_confidence_penalty', 0)
        
        if conf_boost < 0 or conf_boost > 50:
            errors.append("news_confidence_boost must be between 0 and 50")
        if conf_penalty < 0 or conf_penalty > 50:
            errors.append("news_confidence_penalty must be between 0 and 50")
        
        # Source weights validation
        weights = config.get('source_weights', {})
        for source, weight in weights.items():
            if not isinstance(weight, (int, float)) or weight < 0 or weight > 2:
                errors.append(f"source_weights[{source}] must be between 0 and 2")
        
        return errors

# Global configuration manager instance
config_manager = ConfigurationManager()
```

## 🎯 **USAGE IN ENHANCED GENERATOR**

```python
# apps/analysis/enhanced_trading_signals.py (Updated)
from apps.analysis.config_manager import config_manager

class EnhancedDailyTradingSignalGenerator(DailyTradingSignalGenerator):
    
    def __init__(self):
        super().__init__()
        self.news_analyzer = NewsImpactAnalyzer()
        # Configuration loaded dynamically
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from ConfigurationManager."""
        config = config_manager.get_active_config()
        
        # Set instance variables from config
        self.NEWS_SENTIMENT_BOOST_THRESHOLD = config['news_sentiment_boost_threshold']
        self.NEWS_SENTIMENT_PENALTY_THRESHOLD = config['news_sentiment_penalty_threshold']  
        self.HIGH_IMPACT_NEWS_MULTIPLIER = config['high_impact_news_multiplier']
        self.NEWS_CONFIDENCE_BOOST = Decimal(str(config['news_confidence_boost']))
        self.NEWS_CONFIDENCE_PENALTY = Decimal(str(config['news_confidence_penalty']))
        self.NEWS_ANALYSIS_WINDOW_DAYS = config['news_analysis_window_days']
        
        # Feature flags
        self.enable_signal_modification = config['enable_signal_modification']
        self.enable_confidence_adjustment = config['enable_confidence_adjustment']
        self.enable_hold_to_buy_conversion = config['enable_hold_to_buy_conversion']
        self.enable_buy_to_hold_conversion = config['enable_buy_to_hold_conversion']
        
        # Pass source weights to news analyzer
        self.news_analyzer.set_source_weights(config['source_weights'])
        
        logger.info(f"Enhanced Signal Generator loaded config: {config['name']}")
    
    def generate_signals_for_stock(self, stock, trading_session=None):
        """
        Generate enhanced signals with dynamic configuration.
        Configuration is reloaded automatically every 5 minutes.
        """
        # Reload config if cache expired (handled by config_manager)
        current_config = config_manager.get_active_config()
        if current_config['name'] != getattr(self, '_current_config_name', None):
            self._load_configuration()
            self._current_config_name = current_config['name']
        
        # Continue with enhanced signal generation...
        return super().generate_signals_for_stock(stock, trading_session)
```

## 🖥️ **ADMIN INTERFACE** 

```python
# apps/analysis/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from apps.analysis.models import EnhancedSignalConfig

@admin.register(EnhancedSignalConfig)
class EnhancedSignalConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'is_active', 'sentiment_thresholds', 'confidence_adjustments',
        'feature_flags', 'created_at', 'config_actions'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('News Analysis Thresholds', {
            'fields': (
                'news_sentiment_boost_threshold',
                'news_sentiment_penalty_threshold', 
                'high_impact_news_multiplier',
                'news_analysis_window_days'
            )
        }),
        ('Confidence Adjustments', {
            'fields': ('news_confidence_boost', 'news_confidence_penalty')
        }),
        ('Source Configuration', {
            'fields': ('source_weights',),
            'classes': ('collapse',)
        }),
        ('Feature Flags', {
            'fields': (
                'enable_signal_modification',
                'enable_confidence_adjustment',
                'enable_hold_to_buy_conversion',
                'enable_buy_to_hold_conversion'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    def sentiment_thresholds(self, obj):
        return f"Boost: {obj.news_sentiment_boost_threshold} | Penalty: {obj.news_sentiment_penalty_threshold}"
    sentiment_thresholds.short_description = "Sentiment Thresholds"
    
    def confidence_adjustments(self, obj):
        return f"Boost: {obj.news_confidence_boost}% | Penalty: {obj.news_confidence_penalty}%"
    confidence_adjustments.short_description = "Confidence Adjustments"
    
    def feature_flags(self, obj):
        flags = []
        if obj.enable_signal_modification: flags.append("Signal Mod")
        if obj.enable_confidence_adjustment: flags.append("Conf Adj") 
        if obj.enable_hold_to_buy_conversion: flags.append("H→B")
        if obj.enable_buy_to_hold_conversion: flags.append("B→H")
        return " | ".join(flags) if flags else "None"
    feature_flags.short_description = "Features"
    
    def config_actions(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">● ACTIVE</span>')
        else:
            activate_url = reverse('admin:activate_config', args=[obj.pk])
            return format_html(
                '<a href="{}" style="color: blue;">Activate</a>',
                activate_url
            )
    config_actions.short_description = "Actions"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new config
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        
        # If activating this config, deactivate others
        if obj.is_active:
            EnhancedSignalConfig.objects.exclude(pk=obj.pk).update(is_active=False)
```

## 📊 **CONFIGURATION DASHBOARD**

```python
# apps/analysis/views.py - Configuration management view
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from apps.analysis.models import EnhancedSignalConfig
from apps.analysis.config_manager import config_manager

@staff_member_required
def config_dashboard(request):
    """Dashboard for managing Enhanced Signal configurations."""
    
    configs = EnhancedSignalConfig.objects.all().order_by('-created_at')
    active_config = config_manager.get_active_config()
    
    # Validate current active config
    validation_errors = config_manager.validate_config(active_config)
    
    context = {
        'configs': configs,
        'active_config': active_config,
        'validation_errors': validation_errors,
        'profiles': {
            'Conservative': CONSERVATIVE_CONFIG,
            'Balanced': BALANCED_CONFIG,  
            'Aggressive': AGGRESSIVE_CONFIG
        }
    }
    
    return render(request, 'admin/enhanced_config_dashboard.html', context)

@staff_member_required  
def activate_config(request, config_id):
    """Activate specific configuration."""
    config = get_object_or_404(EnhancedSignalConfig, pk=config_id)
    
    # Validate before activation
    config_dict = config_manager._model_to_dict(config)
    errors = config_manager.validate_config(config_dict)
    
    if errors:
        messages.error(request, f"Configuration validation failed: {', '.join(errors)}")
    else:
        config.activate()
        messages.success(request, f"Configuration '{config.name}' activated successfully!")
    
    return redirect('admin:config_dashboard')
```

---

## 🎯 **READY FOR IMPLEMENTATION!**

Ta konfiguracja zapewnia:

✅ **Flexible Parameter Management** - Łatwa zmiana parametrów bez deploymentu  
✅ **Hot Configuration Reloading** - Zmiany widoczne w 5 minut  
✅ **Multiple Profiles** - Conservative/Balanced/Aggressive presets  
✅ **Validation** - Zabezpieczenia przed błędnymi konfiguracjami  
✅ **Admin Interface** - Friendly UI dla non-technical users  
✅ **A/B Testing Ready** - Łatwe przełączanie między konfiguracjami  

**Następny krok:** Implementacja `EnhancedDailyTradingSignalGenerator` z tym systemem konfiguracji! 🚀
