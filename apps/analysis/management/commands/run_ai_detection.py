"""
Django management command for running AI anomaly detection.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, date, timedelta
from apps.core.models import StockSymbol, TradingSession
from apps.analysis.ai_detection import AnomalyDetector, PatternRecognizer
from apps.analysis.models import AnomalyAlert, PatternDetection


class Command(BaseCommand):
    help = 'Run AI anomaly detection for stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-date',
            type=str,
            help='Trading session date (YYYY-MM-DD). Default: today',
        )
        parser.add_argument(
            '--stock-symbol',
            type=str,
            help='Specific stock symbol to analyze. Default: all stocks',
        )
        parser.add_argument(
            '--confidence-threshold',
            type=float,
            default=0.75,
            help='Minimum confidence threshold for alerts (0.0-1.0). Default: 0.75',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be detected without saving to database',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        # Parse session date
        if options['session_date']:
            try:
                session_date = datetime.strptime(options['session_date'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid date format. Use YYYY-MM-DD')
        else:
            session_date = date.today()

        # Get trading session
        try:
            trading_session = TradingSession.objects.get(date=session_date)
        except TradingSession.DoesNotExist:
            raise CommandError(f'No trading session found for {session_date}')

        self.stdout.write(
            self.style.SUCCESS(f'Starting AI anomaly detection for session: {trading_session}')
        )

        # Initialize AI engines
        anomaly_detector = AnomalyDetector()
        pattern_recognizer = PatternRecognizer()

        # Set confidence threshold
        anomaly_detector.default_confidence_threshold = options['confidence_threshold']

        # Get stocks to analyze
        if options['stock_symbol']:
            try:
                stocks = [StockSymbol.objects.get(symbol=options['stock_symbol'])]
            except StockSymbol.DoesNotExist:
                raise CommandError(f'Stock symbol "{options["stock_symbol"]}" not found')
        else:
            # Get all active stocks
            stocks = StockSymbol.objects.filter(is_active=True)

        if options['verbose']:
            self.stdout.write(f'Analyzing {len(stocks)} stocks...')

        total_anomalies = 0
        total_patterns = 0
        processed_stocks = 0

        # Process each stock
        for stock in stocks:
            try:
                if options['verbose']:
                    self.stdout.write(f'Processing {stock.symbol}...')

                # Detect anomalies
                if not options['dry_run']:
                    anomalies_count = anomaly_detector.process_stock_anomalies(stock, trading_session)
                    total_anomalies += anomalies_count
                else:
                    # Dry run - just get anomalies without saving
                    price_anomalies = anomaly_detector.detect_price_anomalies(stock, trading_session)
                    volume_anomalies = anomaly_detector.detect_volume_anomalies(stock, trading_session)
                    pattern_breaks = anomaly_detector.detect_pattern_breaks(stock, trading_session)
                    
                    all_anomalies = price_anomalies + volume_anomalies + pattern_breaks
                    high_confidence_anomalies = [
                        a for a in all_anomalies 
                        if a['confidence'] >= options['confidence_threshold']
                    ]
                    
                    total_anomalies += len(high_confidence_anomalies)
                    
                    if options['verbose'] and high_confidence_anomalies:
                        for anomaly in high_confidence_anomalies:
                            self.stdout.write(
                                f'  - {anomaly["type"]}: {anomaly["description"]} '
                                f'(confidence: {anomaly["confidence"]:.2f})'
                            )

                # Detect patterns
                patterns = pattern_recognizer.detect_candlestick_patterns(stock, trading_session)
                
                if not options['dry_run']:
                    # Save patterns to database
                    for pattern in patterns:
                        PatternDetection.objects.create(
                            stock=stock,
                            trading_session=trading_session,
                            pattern_type=pattern['type'],
                            pattern_category=pattern['category'],
                            confidence_score=pattern['confidence'],
                            description=pattern['description'],
                            pattern_details=pattern['details']
                        )
                    total_patterns += len(patterns)
                else:
                    total_patterns += len(patterns)
                    
                    if options['verbose'] and patterns:
                        for pattern in patterns:
                            self.stdout.write(
                                f'  - Pattern: {pattern["type"]} - {pattern["description"]} '
                                f'(confidence: {pattern["confidence"]:.2f})'
                            )

                processed_stocks += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing {stock.symbol}: {str(e)}')
                )
                if options['verbose']:
                    import traceback
                    self.stdout.write(traceback.format_exc())

        # Summary
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN COMPLETE:\n'
                    f'Processed: {processed_stocks} stocks\n'
                    f'Would detect: {total_anomalies} anomalies\n'
                    f'Would detect: {total_patterns} patterns\n'
                    f'Confidence threshold: {options["confidence_threshold"]:.2f}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'AI DETECTION COMPLETE:\n'
                    f'Processed: {processed_stocks} stocks\n'
                    f'Detected: {total_anomalies} anomalies\n'
                    f'Detected: {total_patterns} patterns\n'
                    f'Session: {trading_session}'
                )
            )

        # Show recent alerts if verbose
        if options['verbose'] and not options['dry_run'] and total_anomalies > 0:
            self.stdout.write('\nRecent high-severity alerts:')
            recent_alerts = AnomalyAlert.objects.filter(
                trading_session=trading_session,
                severity__gte=4
            ).order_by('-confidence_score')[:5]
            
            for alert in recent_alerts:
                self.stdout.write(
                    f'  - {alert.stock.symbol}: {alert.description} '
                    f'(severity: {alert.severity}, confidence: {alert.confidence_score:.2f})'
                )
