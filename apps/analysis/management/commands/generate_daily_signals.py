"""
Management command for generating daily trading signals.

This command generates intraday trading signals for all monitored stocks
based on technical analysis optimized for daily trading strategies.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.analysis.daily_trading_signals import DailyTradingSignalService
from apps.core.models import StockSymbol
import json


class Command(BaseCommand):
    help = 'Generate daily trading signals for monitored stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Generate signals for specific stock symbol',
        )
        parser.add_argument(
            '--all-monitored',
            action='store_true',
            help='Generate signals for all monitored stocks',
        )
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='Show detailed signal analysis',
        )
        parser.add_argument(
            '--save-to-file',
            type=str,
            help='Save results to JSON file',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without creating signals',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🎯 Daily Trading Signal Generator')
        )
        self.stdout.write(f"Generated at: {timezone.localtime().strftime('%H:%M:%S')}")
        
        signal_service = DailyTradingSignalService()
        
        if options['symbol']:
            self._generate_for_symbol(signal_service, options)
        elif options['all_monitored']:
            self._generate_for_all_monitored(signal_service, options)
        else:
            self._show_usage()

    def _generate_for_symbol(self, signal_service, options):
        """Generate signals for a specific symbol."""
        symbol = options['symbol'].upper()
        
        try:
            stock = StockSymbol.objects.get(symbol=symbol, is_active=True)
        except StockSymbol.DoesNotExist:
            raise CommandError(f"Stock symbol '{symbol}' not found or not active")
        
        if not stock.is_monitored:
            self.stdout.write(
                self.style.WARNING(f"⚠️  {symbol} is not monitored for trading signals")
            )
            return
        
        self.stdout.write(f"\n=== Analyzing {symbol} ===")
        
        if options['dry_run']:
            self.stdout.write("🔍 DRY RUN - No signals will be saved")
        
        try:
            signal = signal_service.signal_generator.generate_signals_for_stock(stock)
            self._display_signal(signal, options['show_details'])
            
            if options['save_to_file']:
                self._save_to_file([signal], options['save_to_file'])
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error generating signal for {symbol}: {str(e)}")
            )

    def _generate_for_all_monitored(self, signal_service, options):
        """Generate signals for all monitored stocks."""
        monitored_count = StockSymbol.objects.filter(
            is_monitored=True, 
            is_active=True
        ).count()
        
        self.stdout.write(f"\n=== Analyzing {monitored_count} Monitored Stocks ===")
        
        if options['dry_run']:
            self.stdout.write("🔍 DRY RUN - No signals will be saved")
        
        try:
            results = signal_service.generate_signals_for_all_monitored_stocks()
            self._display_summary(results)
            
            if options['show_details']:
                self.stdout.write("\n" + "="*60)
                self.stdout.write("📊 DETAILED SIGNAL ANALYSIS")
                self.stdout.write("="*60)
                
                for signal in results['signals']:
                    self._display_signal(signal, True)
            
            if options['save_to_file']:
                self._save_to_file(results, options['save_to_file'])
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error generating signals: {str(e)}")
            )

    def _display_signal(self, signal, show_details=False):
        """Display individual signal information."""
        symbol = signal['stock']
        action = signal['signal']
        confidence = signal['confidence']
        reason = signal['reason']
        
        # Signal emoji mapping
        emoji_map = {
            'BUY': '🟢',
            'SELL': '🔴', 
            'HOLD': '⚪',
            'ERROR': '❌'
        }
        
        emoji = emoji_map.get(action, '❓')
        
        # Color mapping
        if action == 'BUY':
            style = self.style.SUCCESS
        elif action == 'SELL':
            style = self.style.ERROR
        else:
            style = self.style.WARNING
        
        self.stdout.write(
            style(f"{emoji} {symbol} | {action} | {confidence:.1f}% | {reason}")
        )
        
        if show_details and signal.get('risk_management'):
            risk = signal['risk_management']
            self.stdout.write(f"   💰 Entry: {risk.get('entry_price', 'N/A')} PLN")
            self.stdout.write(f"   🛑 Stop Loss: {risk.get('stop_loss', 'N/A')} PLN (-{risk.get('max_loss_pct', 'N/A')}%)")
            self.stdout.write(f"   🎯 Take Profit: {risk.get('take_profit', 'N/A')} PLN (+{risk.get('target_profit_pct', 'N/A')}%)")
            self.stdout.write(f"   📊 Position Size: {risk.get('position_size_pct', 'N/A')}%")
            
        if show_details and signal.get('indicators'):
            indicators = signal['indicators']
            self.stdout.write("   📈 Technical Indicators:")
            
            if indicators.get('rsi'):
                rsi = indicators['rsi']
                self.stdout.write(f"      RSI: {rsi.get('value', 'N/A'):.1f} ({rsi.get('signal', 'N/A')})")
            
            if indicators.get('macd'):
                macd = indicators['macd']
                self.stdout.write(f"      MACD: {macd.get('histogram', 'N/A'):.4f} ({'Bullish' if macd.get('bullish') else 'Bearish'})")
            
            if indicators.get('bollinger'):
                bb = indicators['bollinger']
                self.stdout.write(f"      BB Position: {bb.get('position', 'N/A')}")
                
        if show_details and signal.get('market_timing'):
            timing = signal['market_timing']
            self.stdout.write(f"   ⏰ Time to Close: {timing.get('time_to_close', 'N/A')}")
            self.stdout.write(f"   📅 Session: {timing.get('trading_session', 'N/A')}")
        
        self.stdout.write("")  # Empty line for readability

    def _display_summary(self, results):
        """Display summary of all signals."""
        summary = results['summary']
        total = results['total_stocks']
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("📊 SIGNAL SUMMARY")
        self.stdout.write("="*50)
        
        self.stdout.write(f"📈 Total Stocks Analyzed: {total}")
        self.stdout.write(
            self.style.SUCCESS(f"🟢 BUY Signals: {summary['buy_signals']}")
        )
        self.stdout.write(
            self.style.ERROR(f"🔴 SELL Signals: {summary['sell_signals']}")
        )
        self.stdout.write(
            self.style.WARNING(f"⚪ HOLD Signals: {summary['hold_signals']}")
        )
        self.stdout.write(f"📊 Average Confidence: {summary['avg_confidence']}%")
        
        # Quick overview of actionable signals
        actionable_signals = []
        for signal in results['signals']:
            if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                actionable_signals.append(signal)
        
        if actionable_signals:
            self.stdout.write(f"\n🎯 HIGH CONFIDENCE SIGNALS ({len(actionable_signals)}):")
            for signal in sorted(actionable_signals, key=lambda x: x['confidence'], reverse=True):
                emoji = '🟢' if signal['signal'] == 'BUY' else '🔴'
                self.stdout.write(
                    f"   {emoji} {signal['stock']} | {signal['signal']} | {signal['confidence']:.1f}%"
                )
        else:
            self.stdout.write("\n⚪ No high-confidence actionable signals at this time")

    def _save_to_file(self, data, filename):
        """Save results to JSON file."""
        try:
            # Convert Decimal and datetime objects to JSON serializable format
            def json_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                elif hasattr(obj, '__float__'):
                    return float(obj)
                elif hasattr(obj, '__str__'):
                    return str(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=json_serializer, ensure_ascii=False)
            
            self.stdout.write(
                self.style.SUCCESS(f"💾 Results saved to: {filename}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error saving to file: {str(e)}")
            )

    def _show_usage(self):
        """Show command usage examples."""
        self.stdout.write("\n📚 Usage Examples:")
        self.stdout.write("="*50)
        self.stdout.write("# Generate signals for all monitored stocks:")
        self.stdout.write("python manage.py generate_daily_signals --all-monitored")
        self.stdout.write("")
        self.stdout.write("# Generate signal for specific stock:")
        self.stdout.write("python manage.py generate_daily_signals --symbol PKN")
        self.stdout.write("")
        self.stdout.write("# Show detailed analysis:")
        self.stdout.write("python manage.py generate_daily_signals --all-monitored --show-details")
        self.stdout.write("")
        self.stdout.write("# Save results to file:")
        self.stdout.write("python manage.py generate_daily_signals --all-monitored --save-to-file signals.json")
        self.stdout.write("")
        self.stdout.write("# Dry run (preview without saving):")
        self.stdout.write("python manage.py generate_daily_signals --all-monitored --dry-run")
