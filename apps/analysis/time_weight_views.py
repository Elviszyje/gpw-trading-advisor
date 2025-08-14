"""
Time-weighted news analysis configuration views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.exceptions import ValidationError
import json
import logging

from .models import TimeWeightConfiguration
from .forms import TimeWeightConfigurationForm

logger = logging.getLogger(__name__)


@staff_member_required
def time_weight_config_dashboard(request):
    """Dashboard for managing time-weighted news analysis configurations"""
    
    configurations = TimeWeightConfiguration.objects.all().order_by('-is_active', 'name')
    active_configs = configurations.filter(is_active=True)
    
    # Configuration statistics
    stats = {
        'total_configs': configurations.count(),
        'active_configs': active_configs.count(),
        'intraday_configs': configurations.filter(trading_style='intraday').count(),
        'swing_configs': configurations.filter(trading_style='swing').count(),
    }
    
    context = {
        'configurations': configurations,
        'active_configs': active_configs,
        'stats': stats,
        'page_title': 'Time-Weighted News Analysis Configuration'
    }
    
    return render(request, 'analysis/time_weight_dashboard.html', context)


@staff_member_required
def time_weight_config_edit(request, config_id=None):
    """Create or edit a time weight configuration"""
    
    if config_id:
        config = get_object_or_404(TimeWeightConfiguration, id=config_id)
        page_title = f'Edit Configuration: {config.name}'
    else:
        config = None
        page_title = 'Create New Configuration'
    
    if request.method == 'POST':
        form = TimeWeightConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            try:
                with transaction.atomic():
                    config = form.save()
                    
                    if config_id:
                        messages.success(
                            request,
                            f'✅ Configuration "{config.name}" updated successfully!'
                        )
                        logger.info(f"User {request.user.username} updated time weight config {config.name}")
                    else:
                        messages.success(
                            request,
                            f'🎉 New configuration "{config.name}" created successfully!'
                        )
                        logger.info(f"User {request.user.username} created time weight config {config.name}")
                    
                    return redirect('analysis:time_weight_dashboard')
                    
            except ValidationError as e:
                messages.error(request, f'❌ Validation error: {e}')
        else:
            messages.error(request, '❌ Please correct the errors below')
    else:
        form = TimeWeightConfigurationForm(instance=config)
    
    # Weight distribution for preview
    preview_data = None
    if config:
        preview_data = {
            'last_15min_weight': float(config.last_15min_weight),
            'last_1hour_weight': float(config.last_1hour_weight),
            'last_4hour_weight': float(config.last_4hour_weight),
            'today_weight': float(config.today_weight),
            'half_life_minutes': config.half_life_minutes,
        }
    
    context = {
        'form': form,
        'config': config,
        'page_title': page_title,
        'preview_data': json.dumps(preview_data) if preview_data else '{}',
    }
    
    return render(request, 'analysis/time_weight_config_form.html', context)


@staff_member_required
@require_http_methods(["POST"])
def time_weight_config_toggle_active(request, config_id):
    """Toggle active status of a configuration via AJAX"""
    
    try:
        config = get_object_or_404(TimeWeightConfiguration, id=config_id)
        config.is_active = not config.is_active
        config.save()
        
        action = "activated" if config.is_active else "deactivated"
        messages.success(
            request,
            f'✅ Configuration "{config.name}" {action}'
        )
        
        return JsonResponse({
            'success': True,
            'is_active': config.is_active,
            'message': f'Configuration {action}'
        })
        
    except Exception as e:
        logger.error(f"Error toggling config status: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@staff_member_required
@require_http_methods(["POST"])
def time_weight_config_duplicate(request, config_id):
    """Duplicate a configuration"""
    
    try:
        original_config = get_object_or_404(TimeWeightConfiguration, id=config_id)
        
        # Create duplicate
        duplicate_config = TimeWeightConfiguration.objects.create(
            name=f"{original_config.name}_copy",
            trading_style=original_config.trading_style,
            is_active=False,  # Always create as inactive
            half_life_minutes=original_config.half_life_minutes,
            last_15min_weight=original_config.last_15min_weight,
            last_1hour_weight=original_config.last_1hour_weight,
            last_4hour_weight=original_config.last_4hour_weight,
            today_weight=original_config.today_weight,
            breaking_news_multiplier=original_config.breaking_news_multiplier,
            market_hours_multiplier=original_config.market_hours_multiplier,
            pre_market_multiplier=original_config.pre_market_multiplier,
            min_impact_threshold=original_config.min_impact_threshold,
        )
        
        messages.success(
            request,
            f'📋 Configuration duplicated as "{duplicate_config.name}"'
        )
        
        logger.info(f"User {request.user.username} duplicated config {original_config.name}")
        
        return JsonResponse({
            'success': True,
            'new_config_id': duplicate_config.id,
            'new_config_name': duplicate_config.name
        })
        
    except Exception as e:
        logger.error(f"Error duplicating config: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@staff_member_required  
@require_http_methods(["POST"])
def time_weight_config_delete(request, config_id):
    """Delete a configuration"""
    
    try:
        config = get_object_or_404(TimeWeightConfiguration, id=config_id)
        config_name = config.name
        
        # Don't allow deleting active configurations
        if config.is_active:
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete active configuration. Deactivate it first.'
            })
        
        config.delete()
        
        messages.success(
            request,
            f'🗑️ Configuration "{config_name}" deleted'
        )
        
        logger.info(f"User {request.user.username} deleted config {config_name}")
        
        return JsonResponse({
            'success': True,
            'message': 'Configuration deleted'
        })
        
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@staff_member_required
@require_http_methods(["POST"])
def validate_weight_distribution_ajax(request):
    """AJAX endpoint to validate weight distribution in real-time"""
    
    try:
        data = json.loads(request.body)
        
        last_15min = float(data.get('last_15min_weight', 0))
        last_1hour = float(data.get('last_1hour_weight', 0))
        last_4hour = float(data.get('last_4hour_weight', 0))
        today = float(data.get('today_weight', 0))
        
        total_weight = last_15min + last_1hour + last_4hour + today
        
        # Validation
        is_valid = abs(total_weight - 1.0) <= 0.05
        
        response_data = {
            'success': True,
            'is_valid': is_valid,
            'total_weight': round(total_weight, 3),
            'difference': round(total_weight - 1.0, 3),
            'message': 'Valid distribution' if is_valid else f'Total weight is {total_weight:.3f}, should be ~1.0'
        }
        
        return JsonResponse(response_data)
        
    except (ValueError, KeyError) as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid input: {e}'
        })


@login_required
def time_weight_config_preview(request):
    """Public preview of time weight configurations for regular users"""
    
    configurations = TimeWeightConfiguration.objects.filter(is_active=True).order_by('name')
    
    context = {
        'configurations': configurations,
        'page_title': 'Time-Weighted News Analysis Configurations',
        'is_preview': True
    }
    
    return render(request, 'analysis/time_weight_preview.html', context)
