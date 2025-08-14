"""
URL configuration for Analytics API endpoints
"""

from django.urls import path, include
from apps.core.views.analytics_views import (
    MarketOverviewView,
    SentimentTrendsView,
    StockAnalysisView,
    IndustryAnalysisView,
    SystemHealthView,
    AlertsView,
    ComprehensiveReportView,
    quick_stats,
    stock_list
)

app_name = 'analytics'

urlpatterns = [
    # Main analytics endpoints
    path('market-overview/', MarketOverviewView.as_view(), name='market_overview'),
    path('sentiment-trends/', SentimentTrendsView.as_view(), name='sentiment_trends'),
    path('stock-analysis/', StockAnalysisView.as_view(), name='stock_analysis_all'),
    path('stock-analysis/<str:symbol>/', StockAnalysisView.as_view(), name='stock_analysis_single'),
    path('industry-analysis/', IndustryAnalysisView.as_view(), name='industry_analysis'),
    path('system-health/', SystemHealthView.as_view(), name='system_health'),
    path('alerts/', AlertsView.as_view(), name='alerts'),
    
    # Comprehensive reports
    path('comprehensive-report/', ComprehensiveReportView.as_view(), name='comprehensive_report'),
    
    # Quick endpoints for dashboard widgets
    path('quick-stats/', quick_stats, name='quick_stats'),
    path('stocks/', stock_list, name='stock_list'),
]
