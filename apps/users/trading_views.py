"""
Trading preferences views for GPW2 Trading Intelligence Platform
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import cast
from decimal import Decimal
import json
import logging

from .models import User, UserTradingPreferences, NotificationPreferences
from .forms import (
    TradingPreferencesForm, 
    NotificationPreferencesForm, 
    QuickSetupForm
)

logger = logging.getLogger(__name__)


@login_required
def trading_preferences_view(request):
    """Main trading preferences management view."""
    user = cast(User, request.user)
    
    # Get or create trading preferences
    try:
        preferences = UserTradingPreferences.objects.get(user=user)
    except UserTradingPreferences.DoesNotExist:
        preferences = UserTradingPreferences.get_default_preferences(user)
    
    if request.method == 'POST':
        form = TradingPreferencesForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, '🎯 Preferencje handlowe zostały zaktualizowane!')
            logger.info(f"User {user.username} updated trading preferences")
            return redirect('users:trading_preferences')
    else:
        form = TradingPreferencesForm(instance=preferences)
    
    # Calculate some stats for display
    context = {
        'form': form,
        'preferences': preferences,
        'stats': {
            'max_single_loss': preferences.available_capital * (preferences.max_loss_percentage / Decimal('100')),
            'max_single_profit': preferences.available_capital * (preferences.target_profit_percentage / Decimal('100')),
            'max_position_value': preferences.available_capital * (preferences.max_position_size_percentage / Decimal('100')),
            'daily_risk_capital': preferences.available_capital * Decimal('0.02'),  # 2% daily risk rule
        }
    }
    
    return render(request, 'users/trading_preferences.html', context)


@login_required
def risk_management_view(request):
    """Risk management settings view."""
    user = cast(User, request.user)
    
    try:
        preferences = UserTradingPreferences.objects.get(user=user)
    except UserTradingPreferences.DoesNotExist:
        preferences = UserTradingPreferences.get_default_preferences(user)
    
    if request.method == 'POST':
        form = TradingPreferencesForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, '🛡️ Ustawienia zarządzania ryzykiem zostały zaktualizowane!')
            logger.info(f"User {user.username} updated risk management settings")
            return redirect('users:risk_management')
    else:
        form = TradingPreferencesForm(instance=preferences)
    
    context = {
        'form': form,
        'preferences': preferences,
    }
    
    return render(request, 'users/risk_management.html', context)


@login_required  
def notification_preferences_view(request):
    """Notification preferences view."""
    user = cast(User, request.user)
    
    try:
        preferences = NotificationPreferences.objects.get(user=user)
    except NotificationPreferences.DoesNotExist:
        preferences = NotificationPreferences.objects.create(user=user)
    
    if request.method == 'POST':
        form = NotificationPreferencesForm(request.POST, instance=preferences, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, '🔔 Preferencje powiadomień zostały zaktualizowane!')
            logger.info(f"User {user.username} updated notification preferences")
            return redirect('users:notification_preferences')
    else:
        form = NotificationPreferencesForm(instance=preferences, user=user)
    
    context = {
        'form': form,
        'preferences': preferences,
    }
    
    return render(request, 'users/notification_preferences.html', context)


@login_required
def send_test_notification(request):
    """Send test notification to user's Telegram."""
    user = cast(User, request.user)
    
    if request.method == 'POST':
        if not user.telegram_chat_id:
            messages.error(request, '❌ Brak skonfigurowanego Telegram Chat ID! Najpierw wprowadź swój Chat ID.')
            return redirect('users:notification_preferences')
        
        try:
            import asyncio
            from apps.notifications.enhanced_notification_service import EnhancedNotificationService
            
            # Create test notification context
            test_context = {
                'user': user,
                'test_message': True,
                'timestamp': timezone.now(),
                'site_name': 'GPW Trading Advisor'
            }
            
            async def send_test():
                service = EnhancedNotificationService()
                
                # Ensure we have a chat_id (type check)
                chat_id = str(user.telegram_chat_id) if user.telegram_chat_id else None
                if not chat_id:
                    return False
                
                success = await service._send_telegram_notification(
                    chat_id=chat_id,
                    template_name='test_notification',
                    context=test_context
                )
                return success
            
            # Run async function
            success = asyncio.run(send_test())
            
            if success:
                messages.success(request, '🎉 Testowe powiadomienie zostało wysłane na Telegram!')
                logger.info(f"Test notification sent to user {user.username} ({user.telegram_chat_id})")
            else:
                messages.error(request, '❌ Nie udało się wysłać testowego powiadomienia. Sprawdź Chat ID.')
                logger.error(f"Failed to send test notification to user {user.username}")
                
        except Exception as e:
            messages.error(request, f'❌ Błąd podczas wysyłania powiadomienia: {str(e)}')
            logger.error(f"Error sending test notification to user {user.username}: {e}")
    
    return redirect('users:notification_preferences')


@login_required
def preferences_wizard_view(request):
    """Quick setup wizard for new users."""
    user = cast(User, request.user)
    
    # Check if user already has preferences
    has_preferences = UserTradingPreferences.objects.filter(user=user).exists()
    
    if request.method == 'POST':
        form = QuickSetupForm(request.POST)
        if form.is_valid():
            # Generate recommended settings
            recommended = form.get_recommended_settings()
            
            # Create or update preferences
            preferences, created = UserTradingPreferences.objects.get_or_create(
                user=user,
                defaults=recommended
            )
            
            if not created:
                # Update existing preferences
                for key, value in recommended.items():
                    setattr(preferences, key, value)
                preferences.save()
            
            messages.success(request, 
                '🚀 Twoje preferencje zostały skonfigurowane! Możesz je zawsze dostosować w ustawieniach.')
            logger.info(f"User {user.username} completed preferences wizard")
            
            return redirect('users:trading_preferences')
    else:
        form = QuickSetupForm()
    
    context = {
        'form': form,
        'has_preferences': has_preferences,
    }
    
    return render(request, 'users/preferences_wizard.html', context)


@login_required
@require_http_methods(["POST"])
def calculate_position_size_ajax(request):
    """AJAX endpoint to calculate position size preview."""
    try:
        data = json.loads(request.body)
        
        capital = Decimal(str(data.get('capital', 0)))
        confidence = Decimal(str(data.get('confidence', 60)))
        max_position_pct = Decimal(str(data.get('max_position_pct', 10)))
        trading_style = data.get('trading_style', 'moderate')
        
        # Calculate position size using similar logic as model
        base_size_pct = max_position_pct * Decimal('0.5')  # Base: 50% of max
        
        # Confidence factor
        confidence_factor = min(confidence / Decimal('100'), Decimal('0.95'))
        
        # Style modifier
        style_modifiers = {
            'conservative': Decimal('0.7'),
            'moderate': Decimal('1.0'),
            'aggressive': Decimal('1.3'),
            'scalping': Decimal('0.8'),
            'swing': Decimal('1.1'),
        }
        style_modifier = style_modifiers.get(trading_style, Decimal('1.0'))
        
        # Calculate final position size
        position_size_pct = base_size_pct * confidence_factor * style_modifier
        position_value = capital * (position_size_pct / Decimal('100'))
        
        # Ensure minimum position value
        position_value = max(position_value, Decimal('500.0'))
        
        return JsonResponse({
            'success': True,
            'position_value': float(position_value.quantize(Decimal('0.01'))),
            'position_percentage': float(position_size_pct.quantize(Decimal('0.01'))),
            'confidence_factor': float(confidence_factor.quantize(Decimal('0.001'))),
            'style_modifier': style_modifier,
        })
        
    except Exception as e:
        logger.error(f"Error calculating position size: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def validate_preferences_ajax(request):
    """AJAX endpoint to validate preferences in real-time."""
    try:
        data = json.loads(request.body)
        
        # Create temporary preferences object for validation
        user = cast(User, request.user)
        temp_preferences = UserTradingPreferences(user=user)
        
        # Set values from form
        for field, value in data.items():
            if hasattr(temp_preferences, field):
                setattr(temp_preferences, field, value)
        
        # Run validation
        try:
            temp_preferences.full_clean()
            return JsonResponse({'success': True, 'errors': {}})
        except ValidationError as e:
            return JsonResponse({
                'success': False, 
                'errors': e.message_dict if hasattr(e, 'message_dict') else {'__all__': [str(e)]}
            })
            
    except Exception as e:
        logger.error(f"Error validating preferences: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def preferences_summary_view(request):
    """Summary view of all user preferences."""
    user = cast(User, request.user)
    
    # Check if user has trading preferences
    try:
        preferences = UserTradingPreferences.objects.get(user=user)
        has_preferences = True
    except UserTradingPreferences.DoesNotExist:
        preferences = None
        has_preferences = False
    
    # Check notification preferences
    try:
        notification_preferences = NotificationPreferences.objects.get(user=user)
    except NotificationPreferences.DoesNotExist:
        notification_preferences = None
    
    context = {
        'has_preferences': has_preferences,
        'preferences': preferences,
        'notification_preferences': notification_preferences,
        'risk_preferences': None,  # We don't have separate risk preferences model yet
    }
    
    return render(request, 'users/preferences_summary.html', context)


@login_required
@require_http_methods(["POST"])
def reset_preferences_view(request):
    """Reset user preferences to defaults."""
    user = cast(User, request.user)
    
    try:
        preferences = UserTradingPreferences.objects.get(user=user)
        preferences.delete()  # This will soft delete
        
        # Create new default preferences
        new_preferences = UserTradingPreferences.get_default_preferences(user)
        
        messages.success(request, '🔄 Preferencje zostały zresetowane do wartości domyślnych.')
        logger.info(f"User {user.username} reset trading preferences")
        
    except UserTradingPreferences.DoesNotExist:
        messages.info(request, 'Brak preferencji do zresetowania.')
    
    return redirect('users:trading_preferences')
