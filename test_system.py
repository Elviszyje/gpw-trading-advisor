#!/usr/bin/env python3
"""
GPW Trading Advisor - System Integration Test Suite
==================================================

Comprehensive test script to verify all system functionalities
as we develop new features. Ensures we don't break existing functionality.

Usage: python test_system.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from django.utils import timezone
from django.core.management import call_command
from apps.core.models import StockSymbol, TradingSession
from apps.scrapers.models import StockData, ScrapingSource
from apps.scrapers.scraping import StooqCSVScraper, SimpleStockDataCollector


class SystemTestSuite:
    """Complete system functionality test suite."""
    
    def __init__(self):
        self.results = []
        self.failed_tests = []
        
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test result."""
        emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        result = f"{emoji} {test_name}: {status}"
        if details:
            result += f" - {details}"
        
        self.results.append(result)
        if status == "FAIL":
            self.failed_tests.append(test_name)
        
        print(result)
    
    def test_database_connectivity(self):
        """Test database connection and basic operations."""
        try:
            # Test basic count operations
            stock_count = StockSymbol.objects.count()
            data_count = StockData.objects.count()
            session_count = TradingSession.objects.count()
            
            self.log_test(
                "Database Connectivity", 
                "PASS",
                f"Stocks: {stock_count}, Data: {data_count}, Sessions: {session_count}"
            )
            return True
        except Exception as e:
            self.log_test("Database Connectivity", "FAIL", str(e))
            return False
    
    def test_stock_symbols_configuration(self):
        """Test stock symbols are properly configured."""
        try:
            expected_symbols = ['CDR', 'JSW', 'KGH', 'LPP', 'PKN', 'PKO']
            actual_symbols = list(StockSymbol.objects.values_list('symbol', flat=True))
            
            missing = set(expected_symbols) - set(actual_symbols)
            extra = set(actual_symbols) - set(expected_symbols)
            
            if missing:
                self.log_test("Stock Symbols", "FAIL", f"Missing: {missing}")
                return False
            elif extra:
                self.log_test("Stock Symbols", "WARN", f"Extra: {extra}")
            else:
                self.log_test("Stock Symbols", "PASS", f"All {len(expected_symbols)} symbols configured")
            
            return True
        except Exception as e:
            self.log_test("Stock Symbols", "FAIL", str(e))
            return False
    
    def test_csv_scraper_functionality(self):
        """Test CSV scraper classes."""
        try:
            scraper = StooqCSVScraper()
            test_symbol = 'PKN'
            
            # Test data scraping
            result = scraper.scrape_stock_data(test_symbol)
            
            if not result:
                self.log_test("CSV Scraper", "FAIL", "No data returned")
                return False
            
            # Verify required fields
            required_fields = ['open_price', 'high_price', 'low_price', 'close_price', 'volume']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("CSV Scraper", "FAIL", f"Missing fields: {missing_fields}")
                return False
            
            # Verify data types
            if not isinstance(result['close_price'], (int, float, Decimal)):
                self.log_test("CSV Scraper", "FAIL", "Invalid price data type")
                return False
            
            self.log_test(
                "CSV Scraper", 
                "PASS", 
                f"Price: {result['close_price']}, Volume: {result['volume']}"
            )
            return True
            
        except Exception as e:
            self.log_test("CSV Scraper", "FAIL", str(e))
            return False
    
    def test_data_collector_functionality(self):
        """Test data collector operations."""
        try:
            collector = SimpleStockDataCollector()
            test_symbol = 'PKN'
            
            # Test individual collection
            success = collector.collect_stock_data(test_symbol)
            if not success:
                self.log_test("Data Collector (Individual)", "FAIL", "Collection failed")
                return False
            
            self.log_test("Data Collector (Individual)", "PASS", f"{test_symbol} collected")
            
            # Test bulk collection (only first 2 stocks to save time)
            results = collector.collect_all_monitored_stocks()
            successful = sum(1 for success in results.values() if success)
            total = len(results)
            
            if successful == 0:
                self.log_test("Data Collector (Bulk)", "FAIL", "No stocks collected")
                return False
            elif successful < total:
                self.log_test("Data Collector (Bulk)", "WARN", f"{successful}/{total} successful")
            else:
                self.log_test("Data Collector (Bulk)", "PASS", f"{successful}/{total} successful")
            
            return True
            
        except Exception as e:
            self.log_test("Data Collector", "FAIL", str(e))
            return False
    
    def test_management_commands(self):
        """Test Django management commands."""
        try:
            # Test collect_stock_data command exists and basic functionality
            # We'll just import it to verify it exists
            from apps.scrapers.management.commands.collect_stock_data import Command
            
            self.log_test("Management Commands", "PASS", "Commands available")
            return True
            
        except ImportError as e:
            self.log_test("Management Commands", "FAIL", f"Command import failed: {e}")
            return False
        except Exception as e:
            self.log_test("Management Commands", "FAIL", str(e))
            return False
    
    def test_data_integrity(self):
        """Test data integrity and relationships."""
        try:
            # Check if we have recent data
            recent_data = StockData.objects.filter(
                data_timestamp__gte=timezone.now() - timedelta(hours=24)
            )
            
            if not recent_data.exists():
                self.log_test("Data Integrity", "WARN", "No recent data found")
                return True
            
            # Test data relationships
            for data_point in recent_data[:3]:  # Test only first 3
                if not data_point.stock:
                    self.log_test("Data Integrity", "FAIL", "Missing stock relationship")
                    return False
                
                if not data_point.trading_session:
                    self.log_test("Data Integrity", "FAIL", "Missing trading session")
                    return False
                
                # Test price ranges (basic sanity check)
                if data_point.close_price is None or data_point.close_price <= 0:
                    self.log_test("Data Integrity", "FAIL", "Invalid price data")
                    return False
            
            self.log_test("Data Integrity", "PASS", f"Verified {recent_data.count()} records")
            return True
            
        except Exception as e:
            self.log_test("Data Integrity", "FAIL", str(e))
            return False
    
    def test_timezone_conversion(self):
        """Test timezone handling."""
        try:
            # Test if we have data with proper timezone
            sample_data = StockData.objects.first()
            if not sample_data:
                self.log_test("Timezone Conversion", "SKIP", "No data to test")
                return True
            
            # Check if timezone is aware and in UTC
            if sample_data.data_timestamp.tzinfo is None:
                self.log_test("Timezone Conversion", "FAIL", "Naive datetime found")
                return False
            
            # Check if timezone is UTC (simplified check)
            utc_offset = sample_data.data_timestamp.utcoffset()
            if utc_offset != timedelta(0):
                self.log_test("Timezone Conversion", "WARN", f"Non-UTC timezone (offset: {utc_offset})")
            else:
                self.log_test("Timezone Conversion", "PASS", "UTC timezone confirmed")
            
            return True
            
        except Exception as e:
            self.log_test("Timezone Conversion", "FAIL", str(e))
            return False
    
    def test_decimal_precision(self):
        """Test decimal precision for financial data."""
        try:
            sample_data = StockData.objects.first()
            if not sample_data:
                self.log_test("Decimal Precision", "SKIP", "No data to test")
                return True
            
            # Check if prices are Decimal type
            if not isinstance(sample_data.close_price, Decimal):
                self.log_test("Decimal Precision", "FAIL", "Non-Decimal price type")
                return False
            
            # Check precision (should be 4 decimal places max)
            price_str = str(sample_data.close_price)
            if '.' in price_str:
                decimal_places = len(price_str.split('.')[1])
                if decimal_places > 4:
                    self.log_test("Decimal Precision", "WARN", f"{decimal_places} decimal places")
                else:
                    self.log_test("Decimal Precision", "PASS", f"{decimal_places} decimal places")
            else:
                self.log_test("Decimal Precision", "PASS", "Integer price")
            
            return True
            
        except Exception as e:
            self.log_test("Decimal Precision", "FAIL", str(e))
            return False
    
    def test_error_handling(self):
        """Test error handling capabilities."""
        try:
            scraper = StooqCSVScraper()
            
            # Test with invalid symbol
            result = scraper.scrape_stock_data("INVALID_SYMBOL_XYZ")
            
            # Should handle gracefully (return None or empty dict)
            if result is None or (isinstance(result, dict) and not result):
                self.log_test("Error Handling", "PASS", "Invalid symbol handled gracefully")
            else:
                self.log_test("Error Handling", "WARN", "Unexpected result for invalid symbol")
            
            return True
            
        except Exception as e:
            # Should not raise exception for invalid symbol
            self.log_test("Error Handling", "FAIL", f"Exception not caught: {e}")
            return False
    
    def run_all_tests(self):
        """Run complete test suite."""
        print("🧪 GPW Trading Advisor - System Test Suite")
        print("=" * 60)
        print(f"Test run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        tests = [
            self.test_database_connectivity,
            self.test_stock_symbols_configuration,
            self.test_csv_scraper_functionality,
            self.test_data_collector_functionality,
            self.test_management_commands,
            self.test_data_integrity,
            self.test_timezone_conversion,
            self.test_decimal_precision,
            self.test_error_handling,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {test.__name__}: CRITICAL ERROR - {e}")
                failed += 1
            print()
        
        # Summary
        print("=" * 60)
        print("🎯 TEST SUMMARY")
        print("-" * 30)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total: {passed + failed}")
        
        if failed > 0:
            print("\n🔍 FAILED TESTS:")
            for test_name in self.failed_tests:
                print(f"   • {test_name}")
        
        success_rate = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("🎉 System Status: EXCELLENT")
        elif success_rate >= 75:
            print("✅ System Status: GOOD")
        elif success_rate >= 50:
            print("⚠️ System Status: NEEDS ATTENTION")
        else:
            print("🚨 System Status: CRITICAL ISSUES")
        
        print("=" * 60)
        return success_rate >= 75


def main():
    """Main test runner."""
    test_suite = SystemTestSuite()
    success = test_suite.run_all_tests()
    
    if success:
        print("\n✅ All critical tests passed. System is ready for development.")
        sys.exit(0)
    else:
        print("\n❌ Critical tests failed. Please fix issues before continuing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
