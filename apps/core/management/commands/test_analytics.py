"""
Django management command for testing analytics functionality
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.services.analytics_service import analytics_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test analytics service functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            type=str,
            choices=['quick', 'full', 'performance'],
            default='quick',
            help='Type of test to run'
        )

    def handle(self, *args, **options):
        test_type = options['test']
        
        self.stdout.write(
            self.style.SUCCESS(f'🧪 Running {test_type} analytics tests...\n')
        )
        
        if test_type == 'quick':
            self.run_quick_tests()
        elif test_type == 'full':
            self.run_full_tests()
        elif test_type == 'performance':
            self.run_performance_tests()
    
    def run_quick_tests(self):
        """Quick functionality tests"""
        tests = [
            ('Market Overview', self.test_market_overview),
            ('System Health', self.test_system_health),
            ('Quick Stats', self.test_quick_stats),
        ]
        
        results = []
        for test_name, test_func in tests:
            self.stdout.write(f"Testing {test_name}...")
            try:
                result = test_func()
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ {test_name}: PASSED")
                )
                results.append((test_name, True, result))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ {test_name}: FAILED - {str(e)}")
                )
                results.append((test_name, False, str(e)))
        
        # Summary
        passed = sum(1 for _, success, _ in results if success)
        total = len(results)
        
        self.stdout.write(f"\n📊 Quick Test Results: {passed}/{total} passed")
        
        if passed == total:
            self.stdout.write(
                self.style.SUCCESS("🎉 All quick tests passed!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {total - passed} tests failed")
            )
    
    def run_full_tests(self):
        """Comprehensive tests"""
        tests = [
            ('Market Overview', self.test_market_overview),
            ('Sentiment Trends', self.test_sentiment_trends),
            ('Stock Analysis', self.test_stock_analysis),
            ('Industry Analysis', self.test_industry_analysis),
            ('System Health', self.test_system_health),
            ('Alerts', self.test_alerts),
        ]
        
        results = []
        for test_name, test_func in tests:
            self.stdout.write(f"Testing {test_name}...")
            try:
                result = test_func()
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ {test_name}: PASSED")
                )
                results.append((test_name, True, result))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ {test_name}: FAILED - {str(e)}")
                )
                results.append((test_name, False, str(e)))
        
        # Summary
        passed = sum(1 for _, success, _ in results if success)
        total = len(results)
        
        self.stdout.write(f"\n📊 Full Test Results: {passed}/{total} passed")
        
        if passed == total:
            self.stdout.write(
                self.style.SUCCESS("🎉 All tests passed!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {total - passed} tests failed")
            )
    
    def run_performance_tests(self):
        """Performance and load tests"""
        import time
        
        tests = [
            ('Market Overview Performance', lambda: self.time_test(analytics_service.get_market_overview, 7)),
            ('Sentiment Trends Performance', lambda: self.time_test(analytics_service.get_sentiment_trends, 7)),
            ('System Health Performance', lambda: self.time_test(analytics_service.get_system_health_metrics)),
        ]
        
        for test_name, test_func in tests:
            self.stdout.write(f"Running {test_name}...")
            try:
                execution_time = test_func()
                status = "✅ GOOD" if execution_time < 2.0 else "⚠️  SLOW" if execution_time < 5.0 else "❌ TOO SLOW"
                self.stdout.write(f"  {status} - {execution_time:.3f}s")
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ FAILED - {str(e)}")
                )
    
    def time_test(self, func, *args):
        """Time a function execution"""
        import time
        start_time = time.time()
        func(*args)
        return time.time() - start_time
    
    def test_market_overview(self):
        """Test market overview functionality"""
        result = analytics_service.get_market_overview(7)
        
        # Validate structure
        required_keys = ['period_days', 'total_articles', 'analyzed_articles', 'coverage_rate']
        for key in required_keys:
            if key not in result:
                raise AssertionError(f"Missing key: {key}")
        
        # Validate data types
        if not isinstance(result['total_articles'], int):
            raise AssertionError("total_articles should be integer")
        
        if not isinstance(result['coverage_rate'], (int, float)):
            raise AssertionError("coverage_rate should be numeric")
        
        return f"Found {result['total_articles']} articles with {result['coverage_rate']}% AI coverage"
    
    def test_sentiment_trends(self):
        """Test sentiment trends functionality"""
        result = analytics_service.get_sentiment_trends(7, 'daily')
        
        # Validate structure
        required_keys = ['granularity', 'period_days', 'sentiment_counts', 'sentiment_scores']
        for key in required_keys:
            if key not in result:
                raise AssertionError(f"Missing key: {key}")
        
        # Validate granularity
        if result['granularity'] != 'daily':
            raise AssertionError("Granularity not set correctly")
        
        return f"Generated {len(result['sentiment_scores'])} sentiment data points"
    
    def test_stock_analysis(self):
        """Test stock analysis functionality"""
        # Test general stock analysis
        result = analytics_service.get_stock_performance_analysis(None, 7)
        
        required_keys = ['period_days', 'stock_count', 'stock_performances']
        for key in required_keys:
            if key not in result:
                raise AssertionError(f"Missing key: {key}")
        
        return f"Analyzed {result['stock_count']} stocks"
    
    def test_industry_analysis(self):
        """Test industry analysis functionality"""
        result = analytics_service.get_industry_analysis(7)
        
        required_keys = ['period_days', 'industries_analyzed', 'industry_performance']
        for key in required_keys:
            if key not in result:
                raise AssertionError(f"Missing key: {key}")
        
        return f"Analyzed {result['industries_analyzed']} industries"
    
    def test_system_health(self):
        """Test system health metrics"""
        result = analytics_service.get_system_health_metrics()
        
        required_keys = ['timestamp', 'scraping_performance', 'ai_analysis_performance', 'data_quality']
        for key in required_keys:
            if key not in result:
                raise AssertionError(f"Missing key: {key}")
        
        # Check scraping performance structure
        scraping = result['scraping_performance']
        if 'success_rate' not in scraping:
            raise AssertionError("Missing success_rate in scraping_performance")
        
        return f"System health: {scraping['success_rate']}% scraping success rate"
    
    def test_alerts(self):
        """Test alerts functionality"""
        result = analytics_service.get_alert_candidates(0.8, 0.7)
        
        required_keys = ['threshold_sentiment', 'threshold_impact', 'positive_alerts', 'negative_alerts', 'alert_count']
        for key in required_keys:
            if key not in result:
                raise AssertionError(f"Missing key: {key}")
        
        return f"Found {result['alert_count']} alert candidates"
    
    def test_quick_stats(self):
        """Test quick stats calculation"""
        from apps.news.models import NewsArticleModel
        from apps.core.models import NewsClassification, ScrapingExecution
        from django.utils import timezone
        
        # Simple counts to verify database access
        total_articles = NewsArticleModel.objects.count()
        total_classifications = NewsClassification.objects.count()
        total_executions = ScrapingExecution.objects.count()
        
        return f"DB access test: {total_articles} articles, {total_classifications} classifications, {total_executions} executions"
