"""
Management command to test time-weighted news analysis for intraday trading
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from apps.core.models import StockSymbol
from apps.analysis.time_weighted_news import NewsTimeWeightAnalyzer
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator


class Command(BaseCommand):
    help = 'Test time-weighted news analysis for intraday trading signals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stocks',
            type=str,
            nargs='+',
            default=['GPW', 'JSW', 'PKN', 'PZU'],
            help='Stock symbols to analyze'
        )
        parser.add_argument(
            '--config',
            type=str,
            default='intraday_default',
            help='Time weight configuration to use'
        )
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='Show detailed analysis for each stock'
        )

    def handle(self, *args, **options):
        """Test time-weighted news analysis"""
        
        stocks = options['stocks']
        config_name = options['config']
        show_details = options['show_details']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🔍 Testing Time-Weighted News Analysis for Intraday Trading'
            )
        )
        self.stdout.write(f'📊 Configuration: {config_name}')
        self.stdout.write(f'📈 Stocks: {", ".join(stocks)}')
        self.stdout.write('=' * 70)
        
        # Initialize analyzers
        news_analyzer = NewsTimeWeightAnalyzer(config_name)
        signal_generator = DailyTradingSignalGenerator()
        
        # Get stock objects
        stock_objects = StockSymbol.objects.filter(
            symbol__in=stocks,
            is_active=True
        )
        
        if not stock_objects.exists():
            self.stdout.write(
                self.style.ERROR('❌ No active stocks found with provided symbols')
            )
            return
        
        results = {
            'total_analyzed': 0,
            'with_news': 0,
            'signals_modified': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0,
        }
        
        current_time = timezone.now()
        
        for stock in stock_objects:
            self.stdout.write(f'\\n📰 Analyzing {stock.symbol}...')
            
            try:
                # Get time-weighted news analysis
                news_analysis = news_analyzer.get_intraday_sentiment_signal(
                    stock, current_time
                )
                
                # Get base technical signal
                base_signal = signal_generator.generate_signals_for_stock(stock)
                
                results['total_analyzed'] += 1
                
                # Display results
                self._display_stock_analysis(
                    stock, base_signal, news_analysis, show_details
                )
                
                # Update statistics
                if news_analysis['sentiment_data']['news_count'] > 0:
                    results['with_news'] += 1
                
                # Determine if news would modify signal
                if self._would_modify_signal(base_signal, news_analysis):
                    results['signals_modified'] += 1
                
                # Count signal types
                signal_type = base_signal.get('signal', 'hold').lower()
                if 'buy' in signal_type:
                    results['buy_signals'] += 1
                elif 'sell' in signal_type:
                    results['sell_signals'] += 1
                else:
                    results['hold_signals'] += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error analyzing {stock.symbol}: {e}')
                )
        
        # Display summary
        self._display_summary(results, config_name)
        
        # Show configuration details
        self._display_configuration(news_analyzer.config)
    
    def _display_stock_analysis(self, stock, base_signal, news_analysis, show_details):
        """Display analysis results for a single stock"""
        
        sentiment_data = news_analysis['sentiment_data']
        news_signal = news_analysis['signal']
        
        # Basic info
        self.stdout.write(f'  🔸 Base Signal: {base_signal.get("signal", "N/A")} '
                         f'(Confidence: {base_signal.get("confidence", 0):.1f}%)')
        
        self.stdout.write(f'  🔸 News Signal: {news_signal}')
        self.stdout.write(f'  🔸 News Count: {sentiment_data["news_count"]}')
        self.stdout.write(f'  🔸 News Confidence: {sentiment_data["confidence"]:.2f}')
        
        if sentiment_data['news_count'] > 0:
            self.stdout.write(f'  🔸 Weighted Sentiment: {sentiment_data["weighted_sentiment_score"]:+.3f}')
            self.stdout.write(f'  🔸 Recent News (4h): {sentiment_data["recent_news_count"]}')
            self.stdout.write(f'  🔸 Breaking News Impact: {sentiment_data["breaking_news_impact"]:.3f}')
            self.stdout.write(f'  🔸 Sentiment Momentum: {sentiment_data["sentiment_momentum"]:+.3f}')
        else:
            self.stdout.write('  🔸 No relevant news found')
        
        if show_details and sentiment_data['news_count'] > 0:
            self._display_detailed_analysis(sentiment_data)
    
    def _display_detailed_analysis(self, sentiment_data):
        """Display detailed news analysis"""
        self.stdout.write('    📋 Detailed Analysis:')
        self.stdout.write(f'      • Total Weight: {sentiment_data["total_weight"]:.3f}')
        self.stdout.write(f'      • Confidence Score: {sentiment_data["confidence"]:.3f}')
        
        if sentiment_data['sentiment_momentum'] != 0:
            momentum_direction = '📈' if sentiment_data['sentiment_momentum'] > 0 else '📉'
            self.stdout.write(f'      • Momentum {momentum_direction}: {sentiment_data["sentiment_momentum"]:+.3f}')
        
        if sentiment_data['breaking_news_impact'] > 0:
            self.stdout.write(f'      • Breaking News 🚨: {sentiment_data["breaking_news_impact"]:.3f}')
    
    def _would_modify_signal(self, base_signal, news_analysis):
        """Determine if news analysis would modify the base signal"""
        sentiment_data = news_analysis['sentiment_data']
        
        # Check if news confidence is sufficient
        if sentiment_data['confidence'] < 0.3:
            return False
        
        # Check if sentiment is strong enough to influence signal
        sentiment_score = abs(sentiment_data['weighted_sentiment_score'])
        if sentiment_score < 0.1:
            return False
        
        # Check for signal conflicts
        base_signal_type = base_signal.get('signal', '').lower()
        news_signal = news_analysis['signal']
        
        # Strong positive news with sell signal = modification
        if news_signal in ['STRONG_BUY', 'BUY'] and 'sell' in base_signal_type:
            return True
        
        # Strong negative news with buy signal = modification  
        if news_signal in ['STRONG_SELL', 'SELL'] and 'buy' in base_signal_type:
            return True
        
        # Strong news with hold signal = potential upgrade/downgrade
        if base_signal_type == 'hold' and sentiment_score > 0.3:
            return True
        
        return False
    
    def _display_summary(self, results, config_name):
        """Display analysis summary"""
        self.stdout.write('\\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 ANALYSIS SUMMARY'))
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'🎯 Configuration: {config_name}')
        self.stdout.write(f'📈 Stocks Analyzed: {results["total_analyzed"]}')
        self.stdout.write(f'📰 Stocks with News: {results["with_news"]}')
        self.stdout.write(f'🔄 Signals Potentially Modified: {results["signals_modified"]}')
        
        self.stdout.write(f'\\n📊 Signal Distribution:')
        self.stdout.write(f'  • BUY: {results["buy_signals"]}')
        self.stdout.write(f'  • SELL: {results["sell_signals"]}')
        self.stdout.write(f'  • HOLD: {results["hold_signals"]}')
        
        if results['total_analyzed'] > 0:
            news_coverage = (results['with_news'] / results['total_analyzed']) * 100
            modification_rate = (results['signals_modified'] / results['total_analyzed']) * 100
            
            self.stdout.write(f'\\n📈 Statistics:')
            self.stdout.write(f'  • News Coverage: {news_coverage:.1f}%')
            self.stdout.write(f'  • Potential Modification Rate: {modification_rate:.1f}%')
    
    def _display_configuration(self, config):
        """Display time weight configuration details"""
        self.stdout.write('\\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('⚙️ TIME WEIGHT CONFIGURATION'))
        self.stdout.write('=' * 70)
        
        self.stdout.write(f'📋 Name: {config.name}')
        self.stdout.write(f'📈 Trading Style: {config.get_trading_style_display()}')
        self.stdout.write(f'⏰ Half-life: {config.half_life_minutes} minutes')
        
        self.stdout.write(f'\\n🕐 Time Periods:')
        self.stdout.write(f'  • Last 15 min: {config.last_15min_weight:.1%}')
        self.stdout.write(f'  • Last 1 hour: {config.last_1hour_weight:.1%}')
        self.stdout.write(f'  • Last 4 hours: {config.last_4hour_weight:.1%}')
        self.stdout.write(f'  • Today: {config.today_weight:.1%}')
        
        self.stdout.write(f'\\n🔥 Impact Multipliers:')
        self.stdout.write(f'  • Breaking News: {config.breaking_news_multiplier:.1f}x')
        self.stdout.write(f'  • Market Hours: {config.market_hours_multiplier:.1f}x')
        self.stdout.write(f'  • Pre-market: {config.pre_market_multiplier:.1f}x')
        
        self.stdout.write(f'\\n🎯 Minimum Impact Threshold: {config.min_impact_threshold:.3f}')
