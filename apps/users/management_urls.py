"""
URLs for management interface
"""

from django.urls import path
from django.shortcuts import redirect
from . import management_views

def management_home(request):
    return redirect('/users/management/companies/')

urlpatterns = [
    # Management home - redirect to companies list
    path('', management_home, name='management_home'),
    
    # Companies management
    path('companies/', management_views.companies_list, name='companies_list'),
    path('companies/<str:symbol>/', management_views.company_detail, name='company_detail'),
    path('companies/<str:symbol>/edit/', management_views.company_edit, name='company_edit'),
    path('companies/<str:symbol>/delete/', management_views.company_delete, name='company_delete'),
    path('companies/<str:symbol>/intraday/<str:date>/', management_views.company_intraday, name='company_intraday'),
    path('companies/<str:symbol>/toggle-monitoring/', 
         management_views.toggle_company_monitoring_ajax, name='toggle_company_monitoring'),
    
    # Scrapers management
    path('scrapers/', management_views.scrapers_list, name='scrapers_list'),
    path('scrapers/<int:scraper_id>/run/', management_views.run_scraper_ajax, name='run_scraper'),
    path('scrapers/<int:scraper_id>/toggle/', management_views.toggle_scraper_ajax, name='toggle_scraper'),
    path('scrapers/<int:schedule_id>/details/', management_views.schedule_details_ajax, name='schedule_details'),
    path('scrapers/<int:schedule_id>/update/', management_views.update_schedule_ajax, name='update_schedule'),
    path('scrapers/start-all/', management_views.start_all_scrapers_ajax, name='start_all_scrapers'),
    path('scrapers/stop-all/', management_views.stop_all_scrapers_ajax, name='stop_all_scrapers'),
    path('scrapers/refresh-logs/', management_views.refresh_logs_ajax, name='refresh_logs'),
    path('scrapers/test-source/<int:source_id>/', management_views.test_source_ajax, name='test_source'),
    path('scrapers/run-stock-scraper/', management_views.run_stock_scraper_ajax, name='run_stock_scraper'),
    
    # Data browser
    path('data/', management_views.data_browser, name='data_browser'),
    path('data/export/', management_views.export_data, name='export_data'),
    path('data/import/', management_views.import_historical_data, name='import_historical_data'),
    
    # System status
    path('status/', management_views.system_status, name='system_status'),
]
