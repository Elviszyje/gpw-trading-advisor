"""
Forms for Calendar Scraping Administration
"""
from django import forms
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import json


class CalendarScrapingForm(forms.Form):
    """
    Form for configuring calendar scraping jobs with date range selection
    """
    name = forms.CharField(
        max_length=200,
        help_text="Name for this scraping job"
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Optional description of the scraping job"
    )
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Start date for calendar events to scrape"
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="End date for calendar events to scrape"
    )
    
    source_urls = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        help_text="One URL per line. Leave empty to use default Bankier.pl calendar",
        required=False
    )
    
    scraping_config = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        help_text="JSON configuration for scraping (advanced users only)"
    )
    
    def clean_start_date(self):
        start_date = self.cleaned_data['start_date']
        if start_date < date.today() - timedelta(days=365):
            raise ValidationError("Start date cannot be more than 1 year in the past")
        return start_date
    
    def clean_end_date(self):
        end_date = self.cleaned_data['end_date']
        if end_date > date.today() + timedelta(days=365):
            raise ValidationError("End date cannot be more than 1 year in the future")
        return end_date
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError("End date must be after start date")
            
            if (end_date - start_date).days > 180:
                raise ValidationError("Date range cannot exceed 6 months")
        
        # Parse source URLs
        source_urls_text = cleaned_data.get('source_urls', '')
        if source_urls_text:
            urls = [url.strip() for url in source_urls_text.split('\n') if url.strip()]
            cleaned_data['source_urls'] = urls
        else:
            # Default to Bankier.pl calendar
            cleaned_data['source_urls'] = ['https://www.bankier.pl/gielda/kalendarium/']
        
        # Parse scraping config JSON
        scraping_config_text = cleaned_data.get('scraping_config', '')
        if scraping_config_text:
            try:
                config = json.loads(scraping_config_text)
                cleaned_data['scraping_config'] = config
            except json.JSONDecodeError:
                raise ValidationError("Scraping configuration must be valid JSON")
        else:
            cleaned_data['scraping_config'] = {}
        
        return cleaned_data


class DateRangeForm(forms.Form):
    """
    Simple form for selecting date ranges in admin views
    """
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=date.today
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=lambda: date.today() + timedelta(weeks=4)
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise ValidationError("End date must be after start date")
        
        return cleaned_data
