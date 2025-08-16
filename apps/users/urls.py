"""
URL configuration for users app authentication
"""

from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import auth_views as views
from . import trading_views

app_name = 'users'

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.RegistrationView.as_view(), name='register'),
    
    # Onboarding
    path('onboarding/', views.onboarding_view, name='onboarding'),
    
    # User Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('watchlist/', views.watchlist_view, name='watchlist'),
    path('api/watchlist-data/', views.watchlist_data_api, name='watchlist_data_api'),
    path('api/toggle-stock-monitoring/<str:symbol>/', views.toggle_stock_monitoring_ajax, name='toggle_stock_monitoring'),
    
    # Profile Management
    path('profile/', views.profile_view, name='profile'),
    path('preferences/', views.preferences_view, name='preferences'),
    
    # Trading Preferences Management
    path('trading-preferences/', trading_views.trading_preferences_view, name='trading_preferences'),
    path('risk-management/', trading_views.risk_management_view, name='risk_management'),
    path('notification-preferences/', trading_views.notification_preferences_view, name='notification_preferences'),
    path('send-test-notification/', trading_views.send_test_notification, name='send_test_notification'),
    path('preferences-wizard/', trading_views.preferences_wizard_view, name='preferences_wizard'),
    path('preferences-summary/', trading_views.preferences_summary_view, name='preferences_summary'),
    path('reset-preferences/', trading_views.reset_preferences_view, name='reset_preferences'),
    
    # Investment Preferences Management
    path('investment-preferences/', trading_views.investment_preferences_view, name='investment_preferences'),
    path('mode-selection/', trading_views.mode_selection_view, name='mode_selection'),
    path('investment-summary/', trading_views.investment_summary_view, name='investment_summary'),
    path('investment-wizard/', trading_views.investment_wizard_view, name='investment_wizard'),
    path('reset-investment-preferences/', trading_views.reset_investment_preferences_view, name='reset_investment_preferences'),
    
    # Trading Preferences AJAX
    path('api/calculate-position-size/', trading_views.calculate_position_size_ajax, name='calculate_position_size'),
    path('api/validate-preferences/', trading_views.validate_preferences_ajax, name='validate_preferences'),
    
    # Management Interface
    path('management/', include('apps.users.management_urls')),
    
    # Password Management
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt',
             success_url='/users/password-reset/done/'
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/users/reset/done/'
         ), 
         name='password_reset_confirm'),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Alerts & Notifications
    path('alerts/', views.alerts_view, name='alerts'),
    path('alerts/<int:alert_id>/read/', views.mark_alert_read, name='mark_alert_read'),
    path('alerts/mark-all-read/', views.mark_all_alerts_read, name='mark_all_alerts_read'),
    
    # Session Management
    path('sessions/', views.sessions_view, name='sessions'),
    path('sessions/<int:session_id>/terminate/', views.terminate_session, name='terminate_session'),
    
    # AJAX endpoints
    path('api/unread-alerts-count/', views.get_unread_alerts_count, name='unread_alerts_count'),
]
