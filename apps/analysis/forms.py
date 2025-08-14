"""
Forms for time-weighted news analysis configuration
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import TimeWeightConfiguration


class TimeWeightConfigurationForm(forms.ModelForm):
    """Form for creating and editing time weight configurations"""
    
    class Meta:
        model = TimeWeightConfiguration
        fields = [
            'name',
            'trading_style', 
            'is_active',
            'half_life_minutes',
            'last_15min_weight',
            'last_1hour_weight',
            'last_4hour_weight',
            'today_weight',
            'breaking_news_multiplier',
            'market_hours_multiplier', 
            'pre_market_multiplier',
            'min_impact_threshold'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., my_custom_intraday'
            }),
            'trading_style': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'half_life_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '10080',  # 7 days
                'step': '1'
            }),
            'last_15min_weight': forms.NumberInput(attrs={
                'class': 'form-control weight-input',
                'min': '0',
                'max': '1',
                'step': '0.01'
            }),
            'last_1hour_weight': forms.NumberInput(attrs={
                'class': 'form-control weight-input',
                'min': '0',
                'max': '1',
                'step': '0.01'
            }),
            'last_4hour_weight': forms.NumberInput(attrs={
                'class': 'form-control weight-input',
                'min': '0',
                'max': '1',
                'step': '0.01'
            }),
            'today_weight': forms.NumberInput(attrs={
                'class': 'form-control weight-input',
                'min': '0',
                'max': '1',
                'step': '0.01'
            }),
            'breaking_news_multiplier': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.5',
                'max': '5.0',
                'step': '0.1'
            }),
            'market_hours_multiplier': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.5',
                'max': '3.0',
                'step': '0.1'
            }),
            'pre_market_multiplier': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.5',
                'max': '2.0',
                'step': '0.1'
            }),
            'min_impact_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.001',
                'max': '0.5',
                'step': '0.001'
            })
        }
        
        labels = {
            'name': 'Configuration Name',
            'trading_style': 'Trading Style',
            'is_active': 'Active Configuration',
            'half_life_minutes': 'Half-Life (minutes)',
            'last_15min_weight': 'Last 15 Minutes Weight',
            'last_1hour_weight': 'Last 1 Hour Weight',
            'last_4hour_weight': 'Last 4 Hours Weight',
            'today_weight': 'Today Weight',
            'breaking_news_multiplier': 'Breaking News Multiplier',
            'market_hours_multiplier': 'Market Hours Multiplier',
            'pre_market_multiplier': 'Pre-Market Multiplier',
            'min_impact_threshold': 'Minimum Impact Threshold'
        }
        
        help_texts = {
            'name': 'Unique identifier for this configuration',
            'trading_style': 'Type of trading strategy this configuration is designed for',
            'is_active': 'Whether this configuration is currently active',
            'half_life_minutes': 'Time in minutes for news impact to decay by 50%',
            'last_15min_weight': 'Weight for news from the last 15 minutes (0.0-1.0)',
            'last_1hour_weight': 'Weight for news from the last hour (0.0-1.0)',
            'last_4hour_weight': 'Weight for news from the last 4 hours (0.0-1.0)', 
            'today_weight': 'Weight for older news from today (0.0-1.0)',
            'breaking_news_multiplier': 'Multiplier for high-impact breaking news (0.5-5.0)',
            'market_hours_multiplier': 'Multiplier during market hours (0.5-3.0)',
            'pre_market_multiplier': 'Multiplier during pre-market hours (0.5-2.0)',
            'min_impact_threshold': 'Minimum impact score to affect signals (0.001-0.5)'
        }
    
    def clean(self):
        """Validate the entire form"""
        cleaned_data = super().clean()
        
        # Validate weight distribution
        weights = [
            cleaned_data.get('last_15min_weight', 0),
            cleaned_data.get('last_1hour_weight', 0),
            cleaned_data.get('last_4hour_weight', 0),
            cleaned_data.get('today_weight', 0)
        ]
        
        total_weight = sum(weights)
        
        if abs(total_weight - 1.0) > 0.05:
            raise ValidationError(
                f'Weight distribution must sum to approximately 1.0. '
                f'Current sum: {total_weight:.3f}'
            )
        
        return cleaned_data
    
    def clean_name(self):
        """Validate configuration name"""
        name = self.cleaned_data['name']
        
        # Check for unique name (excluding current instance if editing)
        queryset = TimeWeightConfiguration.objects.filter(name=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        if queryset.exists():
            raise ValidationError(
                f'Configuration with name "{name}" already exists. '
                'Please choose a different name.'
            )
        
        return name
    
    def clean_half_life_minutes(self):
        """Validate half-life minutes"""
        half_life = self.cleaned_data['half_life_minutes']
        
        if half_life < 1:
            raise ValidationError('Half-life must be at least 1 minute')
        if half_life > 10080:  # 7 days
            raise ValidationError('Half-life cannot exceed 7 days (10080 minutes)')
            
        return half_life
    
    def clean_min_impact_threshold(self):
        """Validate minimum impact threshold"""
        threshold = self.cleaned_data['min_impact_threshold']
        
        if threshold <= 0:
            raise ValidationError('Minimum impact threshold must be positive')
        if threshold > 0.5:
            raise ValidationError('Minimum impact threshold should not exceed 0.5')
            
        return threshold
