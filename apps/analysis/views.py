"""
AI Analysis Dashboard Views for GPW Trading Advisor.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg, Q, Max
from django.core.paginator import Paginator
from datetime import date, timedelta
from typing import Dict, Any

from apps.core.models import StockSymbol, TradingSession
from apps.analysis.models import AnomalyAlert, PatternDetection, PricePrediction, RiskAssessment
from apps.analysis.ai_detection import AnomalyDetector, SmartAlertEngine


@login_required
def ai_dashboard(request):
    """
    Main AI analysis dashboard.
    """
    # Get recent trading session
    latest_session = TradingSession.objects.order_by('-date').first()
    
    if not latest_session:
        return render(request, 'analysis/ai_dashboard.html', {
            'error': 'No trading sessions available'
        })
    
    # Get recent anomalies
    recent_anomalies = AnomalyAlert.objects.filter(
        trading_session__date__gte=latest_session.date - timedelta(days=7)
    ).order_by('-created_at')[:10]
    
    # Get recent patterns
    recent_patterns = PatternDetection.objects.filter(
        trading_session__date__gte=latest_session.date - timedelta(days=7)
    ).order_by('-created_at')[:10]
    
    # Statistics
    stats = {
        'total_anomalies_today': AnomalyAlert.objects.filter(
            trading_session=latest_session
        ).count(),
        'total_patterns_today': PatternDetection.objects.filter(
            trading_session=latest_session
        ).count(),
        'high_severity_alerts': AnomalyAlert.objects.filter(
            trading_session=latest_session,
            severity__gte=4
        ).count(),
        'avg_confidence': AnomalyAlert.objects.filter(
            trading_session=latest_session
        ).aggregate(avg_conf=Avg('confidence_score'))['avg_conf'] or 0,
    }
    
    # Anomaly type distribution
    anomaly_distribution = AnomalyAlert.objects.filter(
        trading_session=latest_session
    ).values('anomaly_type').annotate(count=Count('id')).order_by('-count')
    
    context = {
        'latest_session': latest_session,
        'recent_anomalies': recent_anomalies,
        'recent_patterns': recent_patterns,
        'stats': stats,
        'anomaly_distribution': anomaly_distribution,
    }
    
    return render(request, 'analysis/ai_dashboard.html', context)


@login_required
def anomaly_alerts(request):
    """
    Anomaly alerts listing with filtering.
    """
    # Get filter parameters
    stock_symbol = request.GET.get('stock')
    anomaly_type = request.GET.get('type')
    min_severity = request.GET.get('min_severity', 1)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Build query
    queryset = AnomalyAlert.objects.select_related('stock', 'trading_session')
    
    if stock_symbol:
        queryset = queryset.filter(stock__symbol__icontains=stock_symbol)
    
    if anomaly_type:
        queryset = queryset.filter(anomaly_type=anomaly_type)
    
    if min_severity:
        queryset = queryset.filter(severity__gte=int(min_severity))
    
    if date_from:
        queryset = queryset.filter(trading_session__date__gte=date_from)
    
    if date_to:
        queryset = queryset.filter(trading_session__date__lte=date_to)
    
    # Order by importance
    queryset = queryset.order_by('-severity', '-confidence_score', '-created_at')
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available filter options
    anomaly_types = AnomalyAlert.objects.values_list('anomaly_type', flat=True).distinct()
    recent_stocks = StockSymbol.objects.filter(
        anomaly_alerts__created_at__gte=timezone.now() - timedelta(days=30)
    ).distinct()[:20]
    
    context = {
        'page_obj': page_obj,
        'anomaly_types': anomaly_types,
        'recent_stocks': recent_stocks,
        'current_filters': {
            'stock': stock_symbol,
            'type': anomaly_type,
            'min_severity': min_severity,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'analysis/anomaly_alerts.html', context)


@login_required
def pattern_detection(request):
    """
    Pattern detection results listing.
    """
    # Get filter parameters
    stock_symbol = request.GET.get('stock')
    pattern_type = request.GET.get('type')
    pattern_category = request.GET.get('category')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Build query
    queryset = PatternDetection.objects.select_related('stock', 'trading_session')
    
    if stock_symbol:
        queryset = queryset.filter(stock__symbol__icontains=stock_symbol)
    
    if pattern_type:
        queryset = queryset.filter(pattern_type=pattern_type)
    
    if pattern_category:
        queryset = queryset.filter(pattern_category=pattern_category)
    
    if date_from:
        queryset = queryset.filter(trading_session__date__gte=date_from)
    
    if date_to:
        queryset = queryset.filter(trading_session__date__lte=date_to)
    
    # Order by confidence and recency
    queryset = queryset.order_by('-confidence_score', '-created_at')
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available filter options
    pattern_types = PatternDetection.objects.values_list('pattern_type', flat=True).distinct()
    pattern_categories = PatternDetection.objects.values_list('pattern_category', flat=True).distinct()
    
    context = {
        'page_obj': page_obj,
        'pattern_types': pattern_types,
        'pattern_categories': pattern_categories,
        'current_filters': {
            'stock': stock_symbol,
            'type': pattern_type,
            'category': pattern_category,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'analysis/pattern_detection.html', context)


@login_required
def stock_ai_analysis(request, symbol):
    """
    Detailed AI analysis for a specific stock.
    """
    stock = get_object_or_404(StockSymbol, symbol=symbol)
    
    # Get recent sessions (last 30 days)
    recent_sessions = TradingSession.objects.filter(
        date__gte=date.today() - timedelta(days=30)
    ).order_by('-date')
    
    # Get anomalies for this stock
    anomalies = AnomalyAlert.objects.filter(
        stock=stock,
        trading_session__in=recent_sessions
    ).order_by('-created_at')
    
    # Get patterns for this stock
    patterns = PatternDetection.objects.filter(
        stock=stock,
        trading_session__in=recent_sessions
    ).order_by('-created_at')
    
    # Calculate statistics
    stats = {
        'total_anomalies': anomalies.count(),
        'total_patterns': patterns.count(),
        'avg_confidence': anomalies.aggregate(avg=Avg('confidence_score'))['avg'] or 0,
        'high_severity_count': anomalies.filter(severity__gte=4).count(),
    }
    
    # Recent anomalies by type
    anomaly_by_type = anomalies.values('anomaly_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent patterns by type
    patterns_by_type = patterns.values('pattern_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'stock': stock,
        'recent_anomalies': anomalies[:10],
        'recent_patterns': patterns[:10],
        'stats': stats,
        'anomaly_by_type': anomaly_by_type,
        'patterns_by_type': patterns_by_type,
    }
    
    return render(request, 'analysis/stock_ai_analysis.html', context)


@login_required
def ai_api_anomalies(request):
    """
    API endpoint for anomaly data (AJAX).
    """
    # Get recent anomalies
    anomalies = AnomalyAlert.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).select_related('stock', 'trading_session').order_by('-created_at')
    
    data = []
    for anomaly in anomalies[:50]:  # Limit to 50 recent
        data.append({
            'id': anomaly.pk,
            'stock_symbol': anomaly.stock.symbol,
            'stock_name': anomaly.stock.name,
            'anomaly_type': anomaly.anomaly_type,
            'severity': anomaly.severity,
            'confidence': float(anomaly.confidence_score),
            'description': anomaly.description,
            'session_date': anomaly.trading_session.date.isoformat(),
            'created_at': anomaly.created_at.isoformat(),
            'price_change_percent': float(anomaly.price_change_percent or 0),
            'volume_ratio': float(anomaly.volume_ratio or 0),
        })
    
    return JsonResponse({
        'anomalies': data,
        'total_count': anomalies.count()
    })


@login_required
def ai_api_patterns(request):
    """
    API endpoint for pattern data (AJAX).
    """
    # Get recent patterns
    patterns = PatternDetection.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).select_related('stock', 'trading_session').order_by('-created_at')
    
    data = []
    for pattern in patterns[:50]:  # Limit to 50 recent
        data.append({
            'id': pattern.pk,
            'stock_symbol': pattern.stock.symbol,
            'stock_name': pattern.stock.name,
            'pattern_type': pattern.pattern_type,
            'pattern_category': pattern.pattern_category,
            'confidence': float(pattern.confidence_score),
            'session_date': pattern.trading_session.date.isoformat(),
            'created_at': pattern.created_at.isoformat(),
        })
    
    return JsonResponse({
        'patterns': data,
        'total_count': patterns.count()
    })


@login_required
def ai_api_stats(request):
    """
    API endpoint for AI analysis statistics (AJAX).
    """
    latest_session = TradingSession.objects.order_by('-date').first()
    
    if not latest_session:
        return JsonResponse({'error': 'No trading sessions available'})
    
    # Today's stats
    today_anomalies = AnomalyAlert.objects.filter(trading_session=latest_session)
    today_patterns = PatternDetection.objects.filter(trading_session=latest_session)
    
    # Week stats
    week_ago = latest_session.date - timedelta(days=7)
    week_anomalies = AnomalyAlert.objects.filter(
        trading_session__date__gte=week_ago
    )
    
    # Anomaly distribution
    anomaly_distribution = today_anomalies.values('anomaly_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Severity distribution
    severity_distribution = today_anomalies.values('severity').annotate(
        count=Count('id')
    ).order_by('severity')
    
    stats = {
        'latest_session_date': latest_session.date.isoformat(),
        'today_anomalies': today_anomalies.count(),
        'today_patterns': today_patterns.count(),
        'today_high_severity': today_anomalies.filter(severity__gte=4).count(),
        'week_anomalies': week_anomalies.count(),
        'avg_confidence_today': float(
            today_anomalies.aggregate(avg=Avg('confidence_score'))['avg'] or 0
        ),
        'anomaly_distribution': list(anomaly_distribution),
        'severity_distribution': list(severity_distribution),
        'top_anomaly_stocks': list(
            today_anomalies.values('stock__symbol', 'stock__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
    }
    
    return JsonResponse(stats)


@login_required
def ml_dashboard(request):
    """
    Main ML dashboard.
    """
    context = {
        'now': timezone.now()
    }
    return render(request, 'analysis/ml_dashboard.html', context)


@login_required
def ml_test(request):
    """
    ML testing page.
    """
    stocks = StockSymbol.objects.filter(is_active=True).order_by('symbol')
    sessions = TradingSession.objects.order_by('-date')[:10]
    
    context = {
        'stocks': stocks,
        'sessions': sessions,
        'now': timezone.now()
    }
    
    return render(request, 'analysis/ml_test.html', context)


@login_required
def ml_config(request):
    """
    ML configuration page.
    """
    return render(request, 'analysis/ml_config.html')


@login_required
def ml_monitoring(request):
    """
    ML monitoring and logs page.
    """
    context = {
        'now': timezone.now()
    }
    
    return render(request, 'analysis/ml_monitoring.html', context)


@login_required
def ml_docs(request):
    """
    ML documentation page.
    """
    return render(request, 'analysis/ml_docs.html')


@login_required 
def ml_dashboard_unavailable(request):
    """
    Fallback ML dashboard view when PyTorch is not available.
    """
    return render(request, 'analysis/ml_unavailable.html')
