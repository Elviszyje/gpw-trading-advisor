"""
Forms for GPW2 Trading Intelligence Platform
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from decimal import Decimal

from apps.users.models import (
    User, 
    UserProfile, 
    UserTradingPreferences, 
    NotificationPreferences
)


class CustomLoginForm(AuthenticationForm):
    """Enhanced login form with better styling"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})


class CustomUserCreationForm(UserCreationForm):
    """Enhanced registration form"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')


class TradingPreferencesForm(forms.ModelForm):
    """Form for basic trading preferences"""
    
    class Meta:
        model = UserTradingPreferences
        fields = [
            'available_capital',
            'target_profit_percentage', 
            'max_loss_percentage',
            'min_confidence_threshold',
            'max_position_size_percentage',
            'min_position_value',
            'trading_style',
            'market_conditions_preference',
        ]
        widgets = {
            'available_capital': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Enter amount in PLN'
            }),
            'target_profit_percentage': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.1',
                'min': '0.5',
                'max': '50'
            }),
            'max_loss_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1', 
                'min': '0.5',
                'max': '20'
            }),
            'min_confidence_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '30',
                'max': '95'
            }),
            'max_position_size_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '1',
                'max': '50'
            }),
            'min_position_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '100'
            }),
            'trading_style': forms.Select(attrs={
                'class': 'form-control form-select'
            }),
            'market_conditions_preference': forms.Select(attrs={
                'class': 'form-control form-select'
            }),
        }


class QuickSetupForm(forms.Form):
    """Simplified setup form for new users"""
    
    EXPERIENCE_CHOICES = [
        ('beginner', 'Początkujący (0-1 rok doświadczenia)'),
        ('intermediate', 'Średniozaawansowany (1-3 lata)'),
        ('advanced', 'Zaawansowany (3+ lata)'),
    ]
    
    CAPITAL_CHOICES = [
        ('small', 'Mały kapitał (1,000 - 10,000 PLN)'),
        ('medium', 'Średni kapitał (10,000 - 100,000 PLN)'),  
        ('large', 'Duży kapitał (100,000+ PLN)'),
    ]
    
    RISK_CHOICES = [
        ('conservative', 'Konserwatywny - bezpieczeństwo kapitału'),
        ('moderate', 'Umiarkowany - zbalansowane podejście'),
        ('aggressive', 'Agresywny - wysokie zyski, wysokie ryzyko'),
    ]
    
    experience_level = forms.ChoiceField(
        choices=EXPERIENCE_CHOICES,
        widget=forms.RadioSelect(),
        label="Twoje doświadczenie w handlu"
    )
    
    capital_range = forms.ChoiceField(
        choices=CAPITAL_CHOICES,
        widget=forms.RadioSelect(),
        label="Dostępny kapitał"
    )
    
    risk_tolerance = forms.ChoiceField(
        choices=RISK_CHOICES,
        widget=forms.RadioSelect(), 
        label="Tolerancja ryzyka"
    )
    
    def get_recommended_settings(self):
        """Generate recommended settings based on form choices."""
        experience = self.cleaned_data['experience_level']
        capital_range = self.cleaned_data['capital_range']
        risk_tolerance = self.cleaned_data['risk_tolerance']
        
        # Set base capital amounts
        capital_amounts = {
            'small': Decimal('5000'),
            'medium': Decimal('50000'),
            'large': Decimal('200000'),
        }
        
        # Risk-based parameters
        risk_settings = {
            'conservative': {
                'max_loss_percentage': Decimal('1.5'),
                'target_profit_percentage': Decimal('2.0'),
                'max_position_size_percentage': Decimal('5.0'),
                'min_confidence_threshold': Decimal('75.0'),
                'trading_style': 'conservative',
            },
            'moderate': {
                'max_loss_percentage': Decimal('3.0'),
                'target_profit_percentage': Decimal('4.0'),
                'max_position_size_percentage': Decimal('10.0'),
                'min_confidence_threshold': Decimal('65.0'),
                'trading_style': 'moderate',
            },
            'aggressive': {
                'max_loss_percentage': Decimal('5.0'),
                'target_profit_percentage': Decimal('7.0'),
                'max_position_size_percentage': Decimal('20.0'),
                'min_confidence_threshold': Decimal('55.0'),
                'trading_style': 'aggressive',
            }
        }
        
        # Experience adjustments
        experience_adjustments = {
            'beginner': {
                'confidence_boost': Decimal('10.0'),
                'position_size_reduction': 0.5,
            },
            'intermediate': {
                'confidence_boost': Decimal('5.0'),
                'position_size_reduction': 0.8,
            },
            'advanced': {
                'confidence_boost': Decimal('0.0'),
                'position_size_reduction': 1.0,
            }
        }
        
        # Generate settings
        base_settings = risk_settings[risk_tolerance].copy()
        adjustments = experience_adjustments[experience]
        
        # Apply experience adjustments
        base_settings['min_confidence_threshold'] += adjustments['confidence_boost']
        base_settings['max_position_size_percentage'] *= Decimal(str(adjustments['position_size_reduction']))
        
        # Set capital
        base_settings['available_capital'] = capital_amounts[capital_range]
        base_settings['min_position_value'] = min(Decimal('1000'), base_settings['available_capital'] * Decimal('0.02'))
        
        # Set other defaults
        base_settings.update({
            'market_conditions_preference': 'all_conditions',
            'preferred_holding_time_hours': 6,
            'max_holding_time_hours': 24,
            'min_daily_volume': 10000,
            'min_market_cap_millions': Decimal('100'),
        })
        
        return base_settings


class NotificationPreferencesForm(forms.ModelForm):
    """Form for notification preferences"""
    
    telegram_chat_id = forms.CharField(
        max_length=50,
        required=False,
        help_text="Twój Telegram Chat ID. Aby go uzyskać, napisz do @GPWTradingBot komendę /start",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'np. 123456789'
        })
    )
    
    class Meta:
        model = NotificationPreferences
        fields = [
            'telegram_enabled',
            'daily_summary',
            'stock_alerts',
            'price_targets',
            'trend_changes',
            'volume_alerts',
            'summary_time',
            'quiet_hours_start',
            'quiet_hours_end',
            'weekend_notifications',
        ]
        widgets = {
            'telegram_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'daily_summary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'stock_alerts': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'price_targets': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'trend_changes': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'volume_alerts': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'weekend_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'summary_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'quiet_hours_start': forms.TimeInput(attrs={
                'type': 'time', 
                'class': 'form-control'
            }),
            'quiet_hours_end': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        """Initialize form with user's telegram_chat_id"""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and hasattr(self.user, 'telegram_chat_id'):
            self.fields['telegram_chat_id'].initial = self.user.telegram_chat_id

    def save(self, commit=True):
        """Save form and update user's telegram_chat_id"""
        instance = super().save(commit=commit)
        
        if self.user and 'telegram_chat_id' in self.cleaned_data:
            telegram_chat_id = self.cleaned_data['telegram_chat_id'].strip()
            if telegram_chat_id != self.user.telegram_chat_id:
                self.user.telegram_chat_id = telegram_chat_id or None
                self.user.save(update_fields=['telegram_chat_id'])
        
        return instance

    def clean_telegram_chat_id(self):
        """Validate telegram_chat_id"""
        chat_id = self.cleaned_data.get('telegram_chat_id', '').strip()
        if chat_id and not chat_id.isdigit():
            raise forms.ValidationError("Chat ID musi być liczbą (np. 123456789)")
        return chat_id


class UserProfileForm(forms.ModelForm):
    """Form for user profile updates"""
    
    class Meta:
        model = UserProfile
        fields = [
            'experience_years',
            'investment_focus',
            'risk_tolerance',
            'trading_experience',
            'investment_goals',
            'dark_mode',
            'compact_view',
        ]
        widgets = {
            'experience_years': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '50'
            }),
            'investment_focus': forms.Select(attrs={
                'class': 'form-control'
            }),
            'risk_tolerance': forms.Select(attrs={
                'class': 'form-control'
            }),
            'trading_experience': forms.Select(attrs={
                'class': 'form-control'
            }),
            'investment_goals': forms.Select(attrs={
                'class': 'form-control'
            }),
            'dark_mode': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'compact_view': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class OnboardingForm(forms.Form):
    """Simple onboarding form"""
    
    INVESTMENT_GOALS = [
        ('income', 'Regular Income'),
        ('growth', 'Capital Growth'),
        ('speculation', 'Short-term Trading'),
    ]
    
    investment_goal = forms.ChoiceField(
        choices=INVESTMENT_GOALS,
        widget=forms.RadioSelect(),
        label="Primary Investment Goal"
    )
    
    has_experience = forms.BooleanField(
        required=False,
        label="I have trading experience"
    )
