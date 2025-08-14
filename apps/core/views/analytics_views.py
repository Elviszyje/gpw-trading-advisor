"""
API Views for Advanced Analytics Dashboard
Provides JSON endpoints for analytics data consumption
"""

from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.db import models
from apps.core.services.analytics_service import analytics_service
from apps.core.models import StockSymbol
import json
import logging

logger = logging.getLogger(__name__)


class BaseAnalyticsView(View):
    """Base view for analytics endpoints"""
    
    def get_query_params(self, request):
        """Extract common query parameters"""
        try:
            days = int(request.GET.get('days', 30))
            if days < 1 or days > 365:
                days = 30
        except (ValueError, TypeError):
            days = 30
        
        return {
            'days': days,
            'granularity': request.GET.get('granularity', 'daily'),
            'export_format': request.GET.get('format', 'json')
        }
    
    def handle_error(self, error_message, status_code=400):
        """Standardized error response"""
        return JsonResponse({
            'success': False,
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        }, status=status_code)


class MarketOverviewView(BaseAnalyticsView):
    """Market overview analytics endpoint"""
    
    def get(self, request):
        try:
            params = self.get_query_params(request)
            data = analytics_service.get_market_overview(params['days'])
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Market overview error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate market overview: {str(e)}", 500)


class SentimentTrendsView(BaseAnalyticsView):
    """Sentiment trends analytics endpoint"""
    
    def get(self, request):
        try:
            params = self.get_query_params(request)
            data = analytics_service.get_sentiment_trends(
                params['days'], 
                params['granularity']
            )
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Sentiment trends error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate sentiment trends: {str(e)}", 500)


class StockAnalysisView(BaseAnalyticsView):
    """Stock performance analysis endpoint"""
    
    def get(self, request, symbol=None):
        try:
            params = self.get_query_params(request)
            
            # Validate symbol if provided
            if symbol:
                symbol = symbol.upper()
                if not StockSymbol.objects.filter(symbol=symbol).exists():
                    return self.handle_error(f"Stock symbol '{symbol}' not found", 404)
            
            data = analytics_service.get_stock_performance_analysis(
                symbol, 
                params['days']
            )
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Stock analysis error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate stock analysis: {str(e)}", 500)


class IndustryAnalysisView(BaseAnalyticsView):
    """Industry analysis endpoint"""
    
    def get(self, request):
        try:
            params = self.get_query_params(request)
            data = analytics_service.get_industry_analysis(params['days'])
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Industry analysis error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate industry analysis: {str(e)}", 500)


class SystemHealthView(BaseAnalyticsView):
    """System health metrics endpoint"""
    
    def get(self, request):
        try:
            data = analytics_service.get_system_health_metrics()
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"System health error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate system health metrics: {str(e)}", 500)


class AlertsView(BaseAnalyticsView):
    """Alert candidates endpoint"""
    
    def get(self, request):
        try:
            # Get thresholds from query params
            try:
                sentiment_threshold = float(request.GET.get('sentiment_threshold', 0.8))
                impact_threshold = float(request.GET.get('impact_threshold', 0.7))
            except (ValueError, TypeError):
                sentiment_threshold = 0.8
                impact_threshold = 0.7
            
            data = analytics_service.get_alert_candidates(
                sentiment_threshold,
                impact_threshold
            )
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Alerts error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate alerts: {str(e)}", 500)


class ComprehensiveReportView(BaseAnalyticsView):
    """Comprehensive analytics report endpoint"""
    
    def get(self, request):
        try:
            params = self.get_query_params(request)
            
            # Generate all analytics
            data = {
                'market_overview': analytics_service.get_market_overview(params['days']),
                'sentiment_trends': analytics_service.get_sentiment_trends(
                    params['days'], 
                    params['granularity']
                ),
                'stock_analysis': analytics_service.get_stock_performance_analysis(
                    None, 
                    params['days']
                ),
                'industry_analysis': analytics_service.get_industry_analysis(params['days']),
                'system_health': analytics_service.get_system_health_metrics(),
                'alerts': analytics_service.get_alert_candidates(),
                'parameters': params
            }
            
            return JsonResponse({
                'success': True,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Comprehensive report error: {str(e)}", exc_info=True)
            return self.handle_error(f"Failed to generate comprehensive report: {str(e)}", 500)


# Function-based views for simple endpoints
@require_http_methods(["GET"])
def quick_stats(request):
    """Quick statistics endpoint for dashboard widgets"""
    try:
        from django.utils import timezone
        from apps.news.models import NewsArticleModel
        from apps.core.models import NewsClassification, ScrapingExecution
        
        # Get quick stats
        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)
        
        stats = {
            'articles_24h': NewsArticleModel.objects.filter(
                scraped_at__gte=last_24h
            ).count(),
            'analyzed_24h': NewsClassification.objects.filter(
                created_at__gte=last_24h
            ).count(),
            'scraping_success_rate': 0,
            'system_status': 'operational'
        }
        
        # Calculate scraping success rate
        recent_executions = ScrapingExecution.objects.filter(
            started_at__gte=last_24h
        )
        if recent_executions.exists():
            successful = recent_executions.filter(success=True).count()
            total = recent_executions.count()
            stats['scraping_success_rate'] = round((successful / total) * 100, 1)
        
        # Determine system status
        if stats['scraping_success_rate'] >= 90:
            stats['system_status'] = 'operational'
        elif stats['scraping_success_rate'] >= 70:
            stats['system_status'] = 'degraded'
        else:
            stats['system_status'] = 'error'
        
        return JsonResponse({
            'success': True,
            'data': stats,
            'timestamp': now.isoformat()
        })
    except Exception as e:
        from django.utils import timezone
        logger.error(f"Quick stats error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@require_http_methods(["GET"])
def stock_list(request):
    """Get list of available stocks for analysis"""
    try:
        from django.utils import timezone
        
        # Get query parameter for search
        search = request.GET.get('search', '').strip()
        
        stocks = StockSymbol.active.all()
        
        if search:
            stocks = stocks.filter(
                models.Q(symbol__icontains=search) | 
                models.Q(name__icontains=search)
            )
        
        # Limit results
        stocks = stocks[:50]
        
        stock_data = [
            {
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': stock.sector,
                'is_monitored': stock.is_monitored
            }
            for stock in stocks
        ]
        
        return JsonResponse({
            'success': True,
            'data': stock_data,
            'count': len(stock_data),
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        from django.utils import timezone
        logger.error(f"Stock list error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)
