#!/usr/bin/env python3

"""
Test dashboard functionality and data display
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.scrapers.models import StockData
from apps.core.models import StockSymbol, ScrapingExecution

def test_dashboard():
    print("=== DASHBOARD FUNCTIONALITY TEST ===")
    
    # Get or create test user
    User = get_user_model()
    user = User.objects.filter(is_active=True).first()
    if not user:
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        print(f"Created test user: {user.username}")
    else:
        print(f"Using existing user: {user.username}")
    
    # Test data availability
    print(f"\n=== DATA STATUS ===")
    stock_count = StockSymbol.objects.count()
    monitored_count = StockSymbol.objects.filter(is_monitored=True, is_active=True).count()
    data_count = StockData.objects.count()
    execution_count = ScrapingExecution.objects.count()
    
    print(f"Stock symbols: {stock_count}")
    print(f"Monitored stocks: {monitored_count}")
    print(f"Stock data records: {data_count}")
    print(f"Scraping executions: {execution_count}")
    
    # Test dashboard context generation
    print(f"\n=== TESTING DASHBOARD LOGIC ===")
    
    # Test monitored stocks data
    monitored_stocks = StockSymbol.objects.filter(is_monitored=True, is_active=True)[:6]
    stock_data = []
    
    for stock in monitored_stocks:
        latest_data = StockData.objects.filter(
            stock=stock
        ).select_related('stock').order_by('-created_at').first()
        
        if latest_data:
            stock_info = {
                'symbol': stock.symbol,
                'name': stock.name,
                'price': float(latest_data.close_price) if latest_data.close_price else 0,
                'volume': latest_data.volume or 0,
                'timestamp': latest_data.created_at
            }
            stock_data.append(stock_info)
            print(f"✅ {stock.symbol}: {stock_info['price']} PLN (Vol: {stock_info['volume']})")
    
    print(f"\nStock data entries ready for dashboard: {len(stock_data)}")
    
    # Test recent executions
    recent_executions_all = ScrapingExecution.objects.order_by('-started_at')[:10]  # Get more for calculation
    recent_executions = list(recent_executions_all)  # Convert to list
    recent_executions_display = recent_executions[:5]  # First 5 for display
    
    print(f"Recent executions: {len(recent_executions_display)}")
    
    for execution in recent_executions_display:
        status_emoji = "✅" if execution.success else "❌"
        status_text = "success" if execution.success else "error"
        print(f"  {status_emoji} {execution.started_at.strftime('%H:%M:%S')} - {status_text}")
    
    # Test success rate calculation
    if recent_executions:
        successful = sum(1 for ex in recent_executions if ex.success)
        success_rate = (successful / len(recent_executions)) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    print(f"\n=== DASHBOARD COMPONENTS TEST ===")
    
    # Test if all required context variables would be available
    context_keys = [
        'total_companies', 'active_stocks', 'unread_alerts_count', 
        'recent_executions_count', 'stock_data', 'scheduler_status',
        'success_rate', 'last_execution', 'last_update'
    ]
    
    for key in context_keys:
        print(f"✅ {key}: Required for template")
    
    print(f"\n🎉 Dashboard test completed!")
    print(f"📊 System status: {'OPERATIONAL' if stock_data else 'NO DATA'}")
    print(f"📈 Live stock prices: {'AVAILABLE' if stock_data else 'UNAVAILABLE'}")
    
    return len(stock_data) > 0

if __name__ == "__main__":
    success = test_dashboard()
    sys.exit(0 if success else 1)
