"""
Authentication forms for GPW2 Trading Intelligence Platform
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from apps.accounts.models import User, UserProfile
from apps.core.models import StockSymbol, Industry


class CustomLoginForm(AuthenticationForm):
    """Enhanced login form with better styling"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Username or Email',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_username(self):
        """Allow login with email or username"""
        username = self.cleaned_data.get('username')
        
        if username and '@' in username:
            # Try to find user by email
            try:
                user = User.objects.get(email=username)
                return user.username
            except User.DoesNotExist:
                pass
        
        return username


class CustomRegistrationForm(UserCreationForm):
    """Enhanced registration form with profile fields"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )
    
    full_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name'
        })
    )
    
    company = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Company (Optional)'
        })
    )
    
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number (Optional)'
        })
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        error_messages={
            'required': 'You must agree to the terms and conditions'
        }
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'full_name', 'company', 'phone_number', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm Password'
        })
    
    def clean_email(self):
        """Ensure email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email
    
    def save(self, commit=True):
        """Save user with additional fields"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.company = self.cleaned_data['company']
        user.phone_number = self.cleaned_data['phone_number']
        
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    
    class Meta:
        model = UserProfile
        fields = [
            'license_number',
            'experience_years',
            'investment_focus',
            'risk_tolerance',
            'portfolio_size_range',
            'dark_mode',
            'compact_view',
            'show_tutorials'
        ]
        widgets = {
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'investment_focus': forms.Select(attrs={'class': 'form-select'}),
            'risk_tolerance': forms.Select(attrs={'class': 'form-select'}),
            'portfolio_size_range': forms.Select(attrs={'class': 'form-select'}),
            'dark_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compact_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_tutorials': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserPreferencesForm(forms.ModelForm):
    """Form for editing user preferences and settings"""
    
    preferred_stocks = forms.ModelMultipleChoiceField(
        queryset=StockSymbol.active.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'multiple': True,
            'data-bs-toggle': 'select2'
        }),
        help_text="Select stocks you want to monitor"
    )
    
    preferred_industries = forms.ModelMultipleChoiceField(
        queryset=Industry.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'multiple': True,
            'data-bs-toggle': 'select2'
        }),
        help_text="Select industries you're interested in"
    )
    
    class Meta:
        model = User
        fields = [
            'email_notifications',
            'sms_notifications',
            'sentiment_alert_threshold',
            'impact_alert_threshold',
            'dashboard_refresh_interval',
            'default_analysis_period',
            'timezone_preference',
            'preferred_stocks',
            'preferred_industries'
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sentiment_alert_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'max': '1.0'
            }),
            'impact_alert_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'max': '1.0'
            }),
            'dashboard_refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '60',
                'max': '3600'
            }),
            'default_analysis_period': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365'
            }),
            'timezone_preference': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add timezone choices
        timezone_choices = [
            ('Europe/Warsaw', 'Warsaw (CET/CEST)'),
            ('UTC', 'UTC'),
            ('Europe/London', 'London (GMT/BST)'),
            ('America/New_York', 'New York (EST/EDT)'),
            ('Asia/Tokyo', 'Tokyo (JST)'),
        ]
        self.fields['timezone_preference'].choices = timezone_choices


class PasswordChangeForm(forms.Form):
    """Custom password change form"""
    
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current Password'
        })
    )
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New Password'
        }),
        help_text="Password must be at least 8 characters long"
    )
    
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm New Password'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        """Validate current password"""
        password = self.cleaned_data.get('current_password')
        if not self.user.check_password(password):
            raise ValidationError('Current password is incorrect.')
        return password
    
    def clean(self):
        """Validate password confirmation"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2:
            if password1 != password2:
                raise ValidationError('New passwords do not match.')
            
            if len(password1) < 8:
                raise ValidationError('Password must be at least 8 characters long.')
        
        return cleaned_data
    
    def save(self):
        """Save new password"""
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        self.user.save()
        return self.user


class OnboardingForm(forms.Form):
    """Onboarding form for new users"""
    
    # Step 1: Trading Experience
    experience_years = forms.IntegerField(
        min_value=0,
        max_value=50,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Years of experience'
        })
    )
    
    investment_focus = forms.ChoiceField(
        choices=[
            ('', 'Select your investment focus'),
            ('growth', 'Growth Stocks'),
            ('value', 'Value Investing'),
            ('dividend', 'Dividend Stocks'),
            ('day_trading', 'Day Trading'),
            ('swing', 'Swing Trading'),
            ('long_term', 'Long-term Investing'),
            ('mixed', 'Mixed Strategy'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    risk_tolerance = forms.ChoiceField(
        choices=[
            ('', 'Select your risk tolerance'),
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('aggressive', 'Aggressive'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Step 2: Interests
    interested_stocks = forms.ModelMultipleChoiceField(
        queryset=StockSymbol.active.filter(is_monitored=True)[:20],  # Top 20 stocks
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    interested_industries = forms.ModelMultipleChoiceField(
        queryset=Industry.objects.all()[:10],  # Top 10 industries
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    # Step 3: Notifications
    notification_preferences = forms.MultipleChoiceField(
        choices=[
            ('email', 'Email Notifications'),
            ('dashboard', 'Dashboard Alerts'),
            ('weekly_summary', 'Weekly Summary Email'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    def save(self, user):
        """Apply onboarding preferences to user"""
        cleaned_data = self.cleaned_data
        
        # Update user preferences
        user.preferred_stocks.set(cleaned_data.get('interested_stocks', []))
        user.preferred_industries.set(cleaned_data.get('interested_industries', []))
        
        # Update notification preferences
        notification_prefs = cleaned_data.get('notification_preferences', [])
        user.email_notifications = 'email' in notification_prefs
        
        # Update profile
        if hasattr(user, 'profile'):
            profile = user.profile
            if cleaned_data.get('experience_years') is not None:
                profile.experience_years = cleaned_data['experience_years']
            if cleaned_data.get('investment_focus'):
                profile.investment_focus = cleaned_data['investment_focus']
            if cleaned_data.get('risk_tolerance'):
                profile.risk_tolerance = cleaned_data['risk_tolerance']
            profile.save()
        
        # Mark onboarding as completed
        user.onboarding_completed = True
        user.profile_completed = True
        user.save()
        
        return user
