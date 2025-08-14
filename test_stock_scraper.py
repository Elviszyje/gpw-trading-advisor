#!/usr/bin/env python3
"""
Test script for the stock scraper AJAX endpoint
"""

import os
import sys
import django
import requests
from django.conf import settings

# Setup Django environment
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

def test_stock_scraper_endpoint():
    """Test the stock scraper AJAX endpoint"""
    print("Testing stock scraper AJAX endpoint...")
    
    # Create a test client
    client = Client()
    
    # First, let's check how many StockData records we have before
    try:
        from apps.scrapers.models import StockData
        before_count = StockData.objects.count()
        print(f"StockData records before scraper: {before_count}")
    except ImportError:
        print("StockData model not available - checking anyway")
        before_count = 0
    
    # Try to find or create a superuser for testing
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser('testadmin', 'test@example.com', 'testpass123')
            print("Created test admin user")
        
        # Login as admin
        client.force_login(admin_user)
        print(f"Logged in as: {admin_user.username}")
        
        # Make the request to the stock scraper endpoint
        response = client.post('/users/management/scrapers/run-stock-scraper/')
        
        print(f"Response status: {response.status_code}")
        print(f"Response content type: {response.get('content-type', 'unknown')}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response JSON: {data}")
                
                if data.get('success'):
                    print(f"✅ Success! {data.get('successful', 0)} successful, {data.get('failed', 0)} failed")
                    print(f"Duration: {data.get('duration', 'unknown')} seconds")
                else:
                    print(f"❌ Request failed: {data.get('error', 'Unknown error')}")
                    
            except ValueError as e:
                print(f"❌ Could not parse JSON response: {e}")
                print(f"Raw response: {response.content.decode()}")
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"Response: {response.content.decode()}")
            
        # Check how many records we have after
        try:
            after_count = StockData.objects.count()
            print(f"StockData records after scraper: {after_count}")
            print(f"New records created: {after_count - before_count}")
        except:
            print("Could not check final record count")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_stock_scraper_endpoint()
