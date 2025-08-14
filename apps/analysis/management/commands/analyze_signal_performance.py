"""
Management command for updating signal performance tracking.
Updates outcomes for pending signals and calculates performance metrics.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta, date
from typing import Optional

from apps.analysis.performance_tracking import SignalPerformanceAnalyzer, BacktestingFramework
from apps.analysis.models import TradingSignal


class Command(BaseCommand):
    help = 'Update signal performance tracking and calculate metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-outcomes',
            action='store_true',
            help='Update outcomes for pending signals'
        )
        
        parser.add_argument(
            '--calculate-performance',
            action='store_true',
            help='Calculate performance metrics'
        )
        
        parser.add_argument(
            '--backtest',
            action='store_true',
            help='Run backtesting analysis'
        )
        
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for analysis (YYYY-MM-DD, default: 30 days ago)'
        )
        
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for analysis (YYYY-MM-DD, default: today)'
        )
        
        parser.add_argument(
            '--symbol',
            type=str,
            help='Specific stock symbol to analyze'
        )
        
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='Show detailed breakdown by stock'
        )

    def handle(self, *args, **options):
        """Execute the performance tracking command."""
        self.stdout.write(
            self.style.SUCCESS('🔍 Starting Signal Performance Analysis...')
        )
        
        # Parse dates
        start_date = self._parse_date(options.get('start_date'))
        end_date = self._parse_date(options.get('end_date'))
        symbol = options.get('symbol')
        
        if start_date is None:
            start_date = (timezone.now() - timedelta(days=30)).date()
        if end_date is None:
            end_date = timezone.now().date()
        
        analyzer = SignalPerformanceAnalyzer()
        
        # Update signal outcomes
        if options['update_outcomes']:
            self._update_signal_outcomes(analyzer)
        
        # Calculate performance metrics
        if options['calculate_performance']:
            self._calculate_performance(analyzer, start_date, end_date, symbol, options['show_details'])
        
        # Run backtesting
        if options['backtest']:
            self._run_backtest(start_date, end_date, symbol)
        
        # If no specific action requested, do everything
        if not any([options['update_outcomes'], options['calculate_performance'], options['backtest']]):
            self._update_signal_outcomes(analyzer)
            self._calculate_performance(analyzer, start_date, end_date, symbol, options['show_details'])
        
        self.stdout.write(
            self.style.SUCCESS('✅ Signal Performance Analysis Complete!')
        )

    def _update_signal_outcomes(self, analyzer: SignalPerformanceAnalyzer):
        """Update outcomes for pending signals."""
        self.stdout.write('📊 Updating pending signal outcomes...')
        
        try:
            results = analyzer.update_signal_outcomes()
            
            self.stdout.write(
                f"✅ Updated {results['updated']} signals"
            )
            self.stdout.write(
                f"⚠️  {results['errors']} errors occurred"
            )
            self.stdout.write(
                f"📈 Processed {results['processed']} pending signals"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error updating outcomes: {str(e)}")
            )

    def _calculate_performance(
        self, 
        analyzer: SignalPerformanceAnalyzer, 
        start_date: date, 
        end_date: date,
        symbol: Optional[str],
        show_details: bool
    ):
        """Calculate and display performance metrics."""
        self.stdout.write(f'📈 Calculating performance metrics from {start_date} to {end_date}...')
        
        try:
            # Overall performance
            metrics = analyzer.calculate_signal_performance(start_date, end_date, symbol)
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write('📊 OVERALL PERFORMANCE METRICS')
            self.stdout.write('='*60)
            
            self.stdout.write(f"📈 Total Signals: {metrics.total_signals}")
            self.stdout.write(f"🟢 Profitable: {metrics.profitable_signals}")
            self.stdout.write(f"🔴 Loss: {metrics.loss_signals}")
            self.stdout.write(f"🟡 Pending: {metrics.pending_signals}")
            self.stdout.write(f"🎯 Win Rate: {metrics.win_rate:.1f}%")
            self.stdout.write(f"💰 Average Return: {metrics.avg_return:.2f}%")
            self.stdout.write(f"📊 Total Return: {metrics.total_return:.2f}%")
            self.stdout.write(f"📉 Max Drawdown: {metrics.max_drawdown:.2f}%")
            self.stdout.write(f"🚀 Best Signal: {metrics.best_signal_return:.2f}%")
            self.stdout.write(f"💥 Worst Signal: {metrics.worst_signal_return:.2f}%")
            if metrics.sharpe_ratio:
                self.stdout.write(f"⚡ Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
            
            # Detailed breakdown by stock
            if show_details and not symbol:
                self.stdout.write('\n' + '='*60)
                self.stdout.write('📋 PERFORMANCE BY STOCK')
                self.stdout.write('='*60)
                
                breakdown = analyzer.get_performance_breakdown_by_stock(start_date, end_date)
                
                for stock_perf in breakdown:
                    self.stdout.write(
                        f"🏢 {stock_perf.symbol:6} | "
                        f"Signals: {stock_perf.total_signals:3} | "
                        f"Win Rate: {stock_perf.win_rate:5.1f}% | "
                        f"Avg Return: {stock_perf.avg_return:6.2f}% | "
                        f"Total: {stock_perf.total_return:6.2f}%"
                    )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error calculating performance: {str(e)}")
            )

    def _run_backtest(self, start_date: date, end_date: date, symbol: Optional[str]):
        """Run backtesting analysis."""
        self.stdout.write(f'🔬 Running backtest from {start_date} to {end_date}...')
        
        try:
            framework = BacktestingFramework()
            symbols = [symbol] if symbol else None
            
            results = framework.run_backtest(
                start_date=start_date,
                end_date=end_date,
                symbols=symbols
            )
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write('🔬 BACKTESTING RESULTS')
            self.stdout.write('='*60)
            
            self.stdout.write(f"💰 Initial Capital: ${results['initial_capital']:,.2f}")
            self.stdout.write(f"💎 Final Capital: ${results['final_capital']:,.2f}")
            self.stdout.write(f"📈 Total Return: {results['total_return']:.2f}%")
            self.stdout.write(f"📊 Total Trades: {results['total_trades']}")
            self.stdout.write(f"🎯 Winning Trades: {results['winning_trades']}")
            self.stdout.write(f"🏆 Win Rate: {results['win_rate']:.1f}%")
            self.stdout.write(f"⚡ Average Trade Return: {results['avg_trade_return']:.2f}%")
            
            # Show best and worst trades
            if results['trades']:
                best_trade = max(results['trades'], key=lambda x: x['return_pct'])
                worst_trade = min(results['trades'], key=lambda x: x['return_pct'])
                
                self.stdout.write(f"\n🚀 Best Trade: {best_trade['stock_symbol']} ({best_trade['return_pct']:.2f}%)")
                self.stdout.write(f"💥 Worst Trade: {worst_trade['stock_symbol']} ({worst_trade['return_pct']:.2f}%)")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error running backtest: {str(e)}")
            )

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")
