"""
Django management command for generating analytics reports
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.services.analytics_service import analytics_service
import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate comprehensive analytics reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to analyze (default: 30)'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to JSON file'
        )
        parser.add_argument(
            '--report',
            type=str,
            choices=['overview', 'sentiment', 'stocks', 'industries', 'health', 'alerts', 'all'],
            default='overview',
            help='Type of report to generate'
        )
        parser.add_argument(
            '--stock',
            type=str,
            help='Analyze specific stock symbol'
        )
        parser.add_argument(
            '--granularity',
            type=str,
            choices=['daily', 'hourly'],
            default='daily',
            help='Time granularity for trends'
        )

    def handle(self, *args, **options):
        days = options['days']
        export_file = options['export']
        report_type = options['report']
        stock_symbol = options['stock']
        granularity = options['granularity']
        
        self.stdout.write(
            self.style.SUCCESS(f'🔬 Generating {report_type} analytics for {days} days...\n')
        )
        
        results = {}
        
        try:
            if report_type in ['overview', 'all']:
                self.stdout.write("📊 Generating market overview...")
                results['market_overview'] = analytics_service.get_market_overview(days)
                self.display_market_overview(results['market_overview'])
            
            if report_type in ['sentiment', 'all']:
                self.stdout.write("📈 Generating sentiment trends...")
                results['sentiment_trends'] = analytics_service.get_sentiment_trends(days, granularity)
                self.display_sentiment_trends(results['sentiment_trends'])
            
            if report_type in ['stocks', 'all'] or stock_symbol:
                self.stdout.write("🏢 Generating stock analysis...")
                results['stock_analysis'] = analytics_service.get_stock_performance_analysis(stock_symbol, days)
                self.display_stock_analysis(results['stock_analysis'], stock_symbol)
            
            if report_type in ['industries', 'all']:
                self.stdout.write("🏭 Generating industry analysis...")
                results['industry_analysis'] = analytics_service.get_industry_analysis(days)
                self.display_industry_analysis(results['industry_analysis'])
            
            if report_type in ['health', 'all']:
                self.stdout.write("⚕️ Generating system health metrics...")
                results['system_health'] = analytics_service.get_system_health_metrics()
                self.display_system_health(results['system_health'])
            
            if report_type in ['alerts', 'all']:
                self.stdout.write("🚨 Generating alert candidates...")
                results['alerts'] = analytics_service.get_alert_candidates()
                self.display_alerts(results['alerts'])
            
            # Export to file if requested
            if export_file:
                self.export_results(results, export_file)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error generating analytics: {str(e)}')
            )
            logger.error(f"Analytics generation failed: {str(e)}", exc_info=True)
    
    def display_market_overview(self, data):
        """Display market overview in formatted way"""
        self.stdout.write(
            self.style.SUCCESS('\n=== MARKET OVERVIEW ===')
        )
        
        self.stdout.write(f"📅 Period: {data['period_days']} days")
        self.stdout.write(f"📰 Total articles: {data['total_articles']:,}")
        self.stdout.write(f"🤖 AI analyzed: {data['analyzed_articles']:,} ({data['coverage_rate']}%)")
        self.stdout.write("")
        
        # Sentiment distribution
        self.stdout.write("😊 Sentiment Distribution:")
        for item in data['sentiment_distribution']:
            if item['sentiment']:
                self.stdout.write(f"  {item['sentiment']}: {item['count']} articles")
        self.stdout.write("")
        
        # Market impact
        self.stdout.write("💥 Market Impact Distribution:")
        for item in data['impact_distribution']:
            if item['market_impact']:
                self.stdout.write(f"  {item['market_impact']}: {item['count']} articles")
        self.stdout.write("")
        
        # Top stocks
        self.stdout.write("🔥 Most Mentioned Stocks:")
        for i, stock in enumerate(data['top_mentioned_stocks'][:5], 1):
            self.stdout.write(f"  {i}. {stock['symbol']} - {stock['name']}: {stock['mentions']} mentions")
        self.stdout.write("")
    
    def display_sentiment_trends(self, data):
        """Display sentiment trends"""
        self.stdout.write(
            self.style.SUCCESS('\n=== SENTIMENT TRENDS ===')
        )
        
        self.stdout.write(f"📅 Period: {data['period_days']} days ({data['granularity']})")
        self.stdout.write(f"📊 Data points: {len(data['sentiment_scores'])}")
        self.stdout.write("")
        
        # Recent sentiment scores
        if data['sentiment_scores']:
            recent_scores = data['sentiment_scores'][-5:]  # Last 5 periods
            self.stdout.write("📈 Recent Sentiment Scores:")
            for score in recent_scores:
                date_str = score['date'].strftime('%Y-%m-%d') if hasattr(score['date'], 'strftime') else str(score['date'])
                avg_sentiment = score['avg_sentiment'] or 0
                self.stdout.write(f"  {date_str}: {avg_sentiment:.3f} ({score['article_count']} articles)")
        
        self.stdout.write("")
    
    def display_stock_analysis(self, data, stock_symbol):
        """Display stock analysis"""
        if 'error' in data:
            self.stdout.write(
                self.style.ERROR(f'\n❌ {data["error"]}')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS('\n=== STOCK ANALYSIS ===')
        )
        
        if stock_symbol:
            # Single stock analysis
            stock = data['stock']
            stats = data['sentiment_stats']
            
            self.stdout.write(f"🏢 Stock: {stock['symbol']} - {stock['name']}")
            self.stdout.write(f"🏭 Sector: {stock['sector'] or 'Unknown'}")
            self.stdout.write(f"📅 Period: {data['period_days']} days")
            self.stdout.write("")
            
            self.stdout.write("📊 Sentiment Statistics:")
            self.stdout.write(f"  Total articles analyzed: {stats['total_articles'] or 0}")
            self.stdout.write(f"  Average sentiment: {stats['avg_sentiment'] or 0:.3f}")
            self.stdout.write(f"  Average confidence: {stats['avg_confidence'] or 0:.3f}")
            self.stdout.write(f"  Average impact: {stats['avg_impact'] or 0:.3f}")
            self.stdout.write("")
            
            # Sentiment distribution
            self.stdout.write("😊 Sentiment Distribution:")
            for item in data['sentiment_distribution']:
                self.stdout.write(f"  {item['sentiment']}: {item['count']} articles")
            self.stdout.write("")
            
            # Recent news
            if data['recent_news']:
                self.stdout.write("📰 Recent News (Top 5):")
                for i, news in enumerate(data['recent_news'][:5], 1):
                    sentiment = news['sentiment'] or 'unknown'
                    score = news['sentiment_score'] or 0
                    self.stdout.write(f"  {i}. {news['title'][:60]}...")
                    self.stdout.write(f"     Sentiment: {sentiment} ({score:.3f})")
                    self.stdout.write("")
        else:
            # Overall stock performance
            self.stdout.write(f"📅 Period: {data['period_days']} days")
            self.stdout.write(f"🏢 Stocks analyzed: {data['stock_count']}")
            self.stdout.write("")
            
            # Top performers
            performances = data['stock_performances']
            if performances:
                self.stdout.write("🚀 Top Sentiment Performers:")
                for i, stock in enumerate(performances[:10], 1):
                    self.stdout.write(
                        f"  {i}. {stock['symbol']} - {stock['name'][:30]}: "
                        f"{stock['avg_sentiment']:.3f} ({stock['mentions']} mentions)"
                    )
                self.stdout.write("")
    
    def display_industry_analysis(self, data):
        """Display industry analysis"""
        self.stdout.write(
            self.style.SUCCESS('\n=== INDUSTRY ANALYSIS ===')
        )
        
        self.stdout.write(f"📅 Period: {data['period_days']} days")
        self.stdout.write(f"🏭 Industries analyzed: {data['industries_analyzed']}")
        self.stdout.write("")
        
        # Top industries by activity
        if data['industry_performance']:
            self.stdout.write("🔥 Most Active Industries:")
            for i, industry in enumerate(data['industry_performance'][:5], 1):
                self.stdout.write(
                    f"  {i}. {industry['industry']}: {industry['article_count']} articles, "
                    f"sentiment: {industry['avg_sentiment']:.3f}"
                )
        self.stdout.write("")
    
    def display_system_health(self, data):
        """Display system health metrics"""
        self.stdout.write(
            self.style.SUCCESS('\n=== SYSTEM HEALTH ===')
        )
        
        self.stdout.write(f"⏰ Report time: {data['timestamp']}")
        self.stdout.write("")
        
        # Scraping performance
        scraping = data['scraping_performance']
        self.stdout.write("🔄 Scraping Performance (24h):")
        self.stdout.write(f"  Executions: {scraping['last_24h_executions']}")
        self.stdout.write(f"  Success rate: {scraping['success_rate']}%")
        self.stdout.write(f"  Items processed: {scraping['items_processed'] or 0}")
        self.stdout.write(f"  Items created: {scraping['items_created'] or 0}")
        self.stdout.write("")
        
        # AI performance
        ai = data['ai_analysis_performance']
        self.stdout.write("🤖 AI Analysis Performance:")
        self.stdout.write(f"  Analyses (24h): {ai['analyses_last_24h']}")
        self.stdout.write(f"  Analyses (7d): {ai['analyses_last_7d']}")
        self.stdout.write(f"  Coverage: {ai['analysis_coverage']}%")
        self.stdout.write("")
        
        # Data quality
        quality = data['data_quality']
        self.stdout.write("📊 Data Quality:")
        self.stdout.write(f"  Total articles: {quality['total_articles']:,}")
        self.stdout.write(f"  Analyzed articles: {quality['analyzed_articles']:,}")
        self.stdout.write(f"  Coverage: {quality['coverage_percentage']}%")
        self.stdout.write("")
        
        # Recent errors
        if data['recent_errors']:
            self.stdout.write(
                self.style.WARNING("⚠️  Recent Errors (5 most recent):")
            )
            for error in data['recent_errors']:
                self.stdout.write(f"  • {error['schedule__name']}: {error['error_message'][:60]}...")
        else:
            self.stdout.write("✅ No recent errors detected")
        
        self.stdout.write("")
    
    def display_alerts(self, data):
        """Display alert candidates"""
        self.stdout.write(
            self.style.SUCCESS('\n=== ALERT CANDIDATES ===')
        )
        
        self.stdout.write(f"🎯 Sentiment threshold: ±{data['threshold_sentiment']}")
        self.stdout.write(f"💥 Impact threshold: {data['threshold_impact']}")
        self.stdout.write(f"🚨 Total alerts: {data['alert_count']}")
        self.stdout.write("")
        
        # Positive alerts
        if data['positive_alerts']:
            self.stdout.write(
                self.style.SUCCESS("🚀 POSITIVE ALERTS:")
            )
            for i, alert in enumerate(data['positive_alerts'][:5], 1):
                stocks = ', '.join(alert['mentioned_stocks']) if alert['mentioned_stocks'] else 'General'
                self.stdout.write(
                    f"  {i}. {alert['title'][:50]}..."
                )
                self.stdout.write(
                    f"     Sentiment: {alert['sentiment_score']:.3f} | "
                    f"Impact: {alert['impact_score']:.3f} | "
                    f"Stocks: {stocks}"
                )
            self.stdout.write("")
        
        # Negative alerts
        if data['negative_alerts']:
            self.stdout.write(
                self.style.ERROR("⚠️  NEGATIVE ALERTS:")
            )
            for i, alert in enumerate(data['negative_alerts'][:5], 1):
                stocks = ', '.join(alert['mentioned_stocks']) if alert['mentioned_stocks'] else 'General'
                self.stdout.write(
                    f"  {i}. {alert['title'][:50]}..."
                )
                self.stdout.write(
                    f"     Sentiment: {alert['sentiment_score']:.3f} | "
                    f"Impact: {alert['impact_score']:.3f} | "
                    f"Stocks: {stocks}"
                )
            self.stdout.write("")
    
    def export_results(self, results, filename):
        """Export results to JSON file"""
        try:
            # Convert datetime objects to strings for JSON serialization
            def datetime_handler(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return str(obj)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=datetime_handler)
            
            self.stdout.write(
                self.style.SUCCESS(f'\n💾 Results exported to: {filename}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Export failed: {str(e)}')
            )
