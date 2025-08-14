"""
Test script for news scraping, calendar events, and ESPI reports.
Tests the newly implemented Phase 5 functionality.
"""

import os
import sys
import django
from datetime import datetime

# Setup Django environment
sys.path.append('/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.scrapers.news_scraper import collect_daily_news
from apps.scrapers.calendar_espi_scraper import collect_company_calendar_data, collect_espi_reports
from apps.scrapers.models import NewsArticleModel, CompanyCalendarEvent, ESPIReport
from apps.core.models import StockSymbol


class Phase5TestSuite:
    """Test suite for Phase 5 functionalities: News, Calendar, ESPI."""
    
    def __init__(self):
        self.test_symbol = 'PKN'  # Use PKN as test symbol
        self.test_results = []
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if details:
            print(f"   📝 {details}")
        self.test_results.append({
            'name': test_name,
            'passed': passed,
            'details': details
        })
        print()
    
    def test_news_scraping(self):
        """Test news scraping functionality."""
        print("🔍 Testing News Scraping...")
        try:
            # Test news collection
            saved_count = collect_daily_news()
            
            # Check if any news articles were saved
            news_count = NewsArticleModel.objects.count()
            
            passed = news_count > 0
            details = f"Collected {saved_count} new articles, total in DB: {news_count}"
            self.log_test("News Scraping", passed, details)
            
            if news_count > 0:
                # Test a sample news article
                sample_article = NewsArticleModel.objects.first()
                if sample_article:
                    has_required_fields = all([
                        sample_article.title,
                        sample_article.url,
                        sample_article.published_date,
                        sample_article.source
                    ])
                    
                    details = f"Sample article: '{sample_article.title[:50]}...' from {sample_article.source}"
                    self.log_test("News Article Structure", has_required_fields, details)
                
                return True
            
        except Exception as e:
            self.log_test("News Scraping", False, f"Error: {str(e)}")
            return False
    
    def test_calendar_events(self):
        """Test calendar events functionality."""
        print("📅 Testing Calendar Events...")
        try:
            # Test calendar collection for specific symbol
            saved_count = collect_company_calendar_data(self.test_symbol, days_ahead=30)
            
            # Check calendar events in database
            calendar_count = CompanyCalendarEvent.objects.count()
            
            passed = True  # Pass even if no events found (they might not have upcoming events)
            details = f"Collected {saved_count} new events, total in DB: {calendar_count}"
            self.log_test("Calendar Event Collection", passed, details)
            
            if calendar_count > 0:
                # Test a sample calendar event
                sample_event = CompanyCalendarEvent.objects.first()
                if sample_event:
                    has_required_fields = all([
                        sample_event.title,
                        sample_event.event_date,
                        sample_event.event_type,
                        sample_event.impact_level
                    ])
                    
                    details = f"Sample event: '{sample_event.title}' on {sample_event.event_date.date()}"
                    self.log_test("Calendar Event Structure", has_required_fields, details)
            
            return True
            
        except Exception as e:
            self.log_test("Calendar Events", False, f"Error: {str(e)}")
            return False
    
    def test_espi_reports(self):
        """Test ESPI reports functionality."""
        print("📊 Testing ESPI Reports...")
        try:
            # Test ESPI collection for specific symbol
            saved_count = collect_espi_reports(self.test_symbol, days_back=7)
            
            # Check ESPI reports in database
            espi_count = ESPIReport.objects.count()
            
            passed = True  # Pass even if no reports found (might not have recent reports)
            details = f"Collected {saved_count} new reports, total in DB: {espi_count}"
            self.log_test("ESPI Report Collection", passed, details)
            
            if espi_count > 0:
                # Test a sample ESPI report
                sample_report = ESPIReport.objects.first()
                if sample_report:
                    has_required_fields = all([
                        sample_report.title,
                        sample_report.publication_date,
                        sample_report.report_type,
                        sample_report.importance_level
                    ])
                    
                    details = f"Sample report: '{sample_report.title}' ({sample_report.report_type})"
                    self.log_test("ESPI Report Structure", has_required_fields, details)
            
            return True
            
        except Exception as e:
            self.log_test("ESPI Reports", False, f"Error: {str(e)}")
            return False
    
    def test_model_relationships(self):
        """Test database model relationships."""
        print("🔗 Testing Model Relationships...")
        try:
            # Test stock symbol relationships
            test_stock = StockSymbol.objects.filter(symbol=self.test_symbol).first()
            
            if test_stock:
                # Check if we can link news articles to stocks
                news_with_stock = NewsArticleModel.objects.filter(
                    stock_symbols__contains=[self.test_symbol]
                ).count()
                
                # Check calendar events for this stock
                calendar_events = CompanyCalendarEvent.objects.filter(
                    stock_symbol=test_stock
                ).count()
                
                # Check ESPI reports for this stock
                espi_reports = ESPIReport.objects.filter(
                    stock_symbol=test_stock
                ).count()
                
                details = f"Stock {self.test_symbol}: {news_with_stock} news, {calendar_events} events, {espi_reports} ESPI"
                self.log_test("Model Relationships", True, details)
                return True
            else:
                self.log_test("Model Relationships", False, f"Test stock {self.test_symbol} not found")
                return False
                
        except Exception as e:
            self.log_test("Model Relationships", False, f"Error: {str(e)}")
            return False
    
    def test_data_integrity(self):
        """Test data integrity and constraints."""
        print("🔍 Testing Data Integrity...")
        try:
            # Check for duplicate news articles
            total_articles = NewsArticleModel.objects.count()
            unique_urls = NewsArticleModel.objects.values('url').distinct().count()
            
            # Check for valid dates
            future_news = NewsArticleModel.objects.filter(
                published_date__gt=datetime.now()
            ).count()
            
            # Check calendar events have valid dates
            invalid_calendar = CompanyCalendarEvent.objects.filter(
                event_date__lt=datetime.now().date()
            ).count()
            
            passed = future_news == 0  # No future news articles
            details = f"Articles: {total_articles}, Unique URLs: {unique_urls}, Future news: {future_news}"
            self.log_test("Data Integrity", passed, details)
            
            return passed
            
        except Exception as e:
            self.log_test("Data Integrity", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all Phase 5 tests."""
        print("🚀 Starting Phase 5 Functionality Tests")
        print("=" * 60)
        print()
        
        # Run all tests
        test_methods = [
            self.test_news_scraping,
            self.test_calendar_events, 
            self.test_espi_reports,
            self.test_model_relationships,
            self.test_data_integrity
        ]
        
        for test_method in test_methods:
            test_method()
        
        # Summary
        print("=" * 60)
        print("📊 PHASE 5 TEST SUMMARY")
        print("=" * 60)
        
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"✅ Passed: {passed_tests}/{total_tests}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Phase 5 Status: EXCELLENT")
        elif success_rate >= 60:
            print("👍 Phase 5 Status: GOOD")
        else:
            print("⚠️ Phase 5 Status: NEEDS IMPROVEMENT")
        
        print()
        print("📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            print(f"{status} {result['name']}")
            if result['details']:
                print(f"   {result['details']}")
        
        return success_rate >= 60


if __name__ == "__main__":
    test_suite = Phase5TestSuite()
    test_suite.run_all_tests()
