"""
URL configuration for AI Analysis app.
"""

from django.urls import path
from . import views, ml_views, recommendation_views, time_weight_views

app_name = 'analysis'

urlpatterns = [
    # AI Dashboard
    path('ai/', views.ai_dashboard, name='ai_dashboard'),
    
    # ML Dashboard and Training
    path('ml/', ml_views.ml_dashboard, name='ml_dashboard'),
    path('ml-test/', ml_views.ml_test, name='ml_test'),
    path('ml-config/', ml_views.ml_config, name='ml_config'),
    path('ml-monitoring/', ml_views.ml_monitoring, name='ml_monitoring'),
    path('ml-docs/', ml_views.ml_docs, name='ml_docs'),
    path('ml/train/', ml_views.train_models, name='train_models'),
    path('ml/feedback/', ml_views.submit_feedback, name='ml_feedback'),
    path('ml/predictions/', ml_views.ml_predictions, name='ml_predictions'),
    path('ml/performance/', ml_views.model_performance, name='model_performance'),
    
    # ML API endpoints
    path('api/ml/predict/', ml_views.GetPredictionView.as_view(), name='api_ml_predict'),
    path('api/ml/logs/', ml_views.api_ml_logs, name='api_ml_logs'),
    path('api/ml/processes/', ml_views.api_ml_processes, name='api_ml_processes'),
    path('api/ml/train/', ml_views.api_ml_train, name='api_ml_train'),
    path('api/ml/training-status/', ml_views.api_ml_training_status, name='api_ml_training_status'),
    path('api/ml/config/', ml_views.api_ml_config, name='api_ml_config'),
    path('api/ml/quick-predict/', ml_views.api_ml_quick_predict, name='api_ml_quick_predict'),
    path('api/ml/reset/', ml_views.api_ml_reset, name='api_ml_reset'),
    path('api/ml/system-resources/', ml_views.api_ml_system_resources, name='api_ml_system_resources'),
    path('api/detect-anomalies/', ml_views.api_detect_anomalies, name='api_detect_anomalies'),
    
    # Recommendation Performance Analysis
    path('recommendations/', recommendation_views.recommendation_dashboard, name='recommendation_dashboard'),
    path('recommendations/details/', recommendation_views.recommendation_details, name='recommendation_details'),
    path('recommendations/learning/', recommendation_views.learning_analytics, name='learning_analytics'),
    path('api/recommendations/stats/', recommendation_views.api_recommendation_stats, name='api_recommendation_stats'),
    
    # Daily Trading API endpoints
    path('daily-trading-api/', recommendation_views.daily_trading_api, name='daily_trading_api'),
    path('recommendations/quality-report/', recommendation_views.recommendation_quality_report, name='recommendation_quality_report'),
    
    # Anomaly Detection
    path('anomalies/', views.anomaly_alerts, name='anomaly_alerts'),
    
    # Pattern Detection
    path('patterns/', views.pattern_detection, name='pattern_detection'),
    
    # Stock-specific AI analysis
    path('stock/<str:symbol>/ai/', views.stock_ai_analysis, name='stock_ai_analysis'),
    path('stock/<str:symbol>/predict/', ml_views.generate_ml_prediction, name='generate_ml_prediction'),
    
    # Time-Weighted News Analysis Configuration
    path('time-weight-config/', time_weight_views.time_weight_config_dashboard, name='time_weight_dashboard'),
    path('time-weight-config/new/', time_weight_views.time_weight_config_edit, name='time_weight_config_new'),
    path('time-weight-config/<int:config_id>/edit/', time_weight_views.time_weight_config_edit, name='time_weight_config_edit'),
    path('time-weight-config/preview/', time_weight_views.time_weight_config_preview, name='time_weight_config_preview'),
    
    # Time Weight Config AJAX endpoints
    path('api/time-weight-config/<int:config_id>/toggle/', time_weight_views.time_weight_config_toggle_active, name='time_weight_config_toggle'),
    path('api/time-weight-config/<int:config_id>/duplicate/', time_weight_views.time_weight_config_duplicate, name='time_weight_config_duplicate'),
    path('api/time-weight-config/<int:config_id>/delete/', time_weight_views.time_weight_config_delete, name='time_weight_config_delete'),
    path('api/validate-weight-distribution/', time_weight_views.validate_weight_distribution_ajax, name='validate_weight_distribution'),
    
    # API endpoints for AJAX
    path('api/anomalies/', views.ai_api_anomalies, name='api_anomalies'),
    path('api/patterns/', views.ai_api_patterns, name='api_patterns'),
    path('api/stats/', views.ai_api_stats, name='api_stats'),
]
