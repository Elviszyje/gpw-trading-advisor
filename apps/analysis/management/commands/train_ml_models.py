"""
Django management command for training ML models.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, date, timedelta
from apps.core.models import StockSymbol, TradingSession
from apps.analysis.ml_models import MLModelManager
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train ML models on historical stock data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            type=str,
            choices=['price_predictor', 'anomaly_detector', 'all'],
            default='all',
            help='Type of model to train. Default: all',
        )
        parser.add_argument(
            '--stocks',
            type=str,
            nargs='*',
            help='Specific stock symbols to train on. Default: all active stocks',
        )
        parser.add_argument(
            '--force-retrain',
            action='store_true',
            help='Force retraining even if models already exist',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
        parser.add_argument(
            '--max-stocks',
            type=int,
            default=50,
            help='Maximum number of stocks to train on (for performance). Default: 50',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting ML model training...')
        )

        # Initialize ML manager
        ml_manager = MLModelManager()
        
        # Get stocks to train on
        if options['stocks']:
            stocks = []
            for symbol in options['stocks']:
                try:
                    stock = StockSymbol.objects.get(symbol=symbol.upper())
                    stocks.append(stock)
                except StockSymbol.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'Stock symbol "{symbol}" not found, skipping...')
                    )
        else:
            # Get active stocks with recent data
            stocks = self._get_stocks_with_data(options['max_stocks'])
        
        if not stocks:
            raise CommandError('No stocks available for training')
        
        self.stdout.write(f'Training on {len(stocks)} stocks...')
        
        model_type = options['model_type']
        force_retrain = options['force_retrain']
        
        results = {}
        
        # Train price predictor
        if model_type in ['price_predictor', 'all']:
            self.stdout.write('Training price prediction model...')
            try:
                result = ml_manager.train_price_predictor(
                    stocks=stocks,
                    force_retrain=force_retrain
                )
                results['price_predictor'] = result
                
                if result['status'] == 'training_completed':
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Price predictor training completed!\n'
                            f'  - Epochs: {result["epochs"]}\n'
                            f'  - Final train loss: {result["final_train_loss"]:.6f}\n'
                            f'  - Final val loss: {result["final_val_loss"]:.6f}\n'
                            f'  - Training samples: {result["training_samples"]}\n'
                            f'  - Test samples: {result["test_samples"]}'
                        )
                    )
                elif result['status'] == 'insufficient_data':
                    self.stdout.write(
                        self.style.WARNING(
                            f'Insufficient training data: {result.get("samples", 0)} samples found'
                        )
                    )
                elif result['status'] == 'model_already_trained':
                    self.stdout.write(
                        self.style.WARNING('Price predictor already trained (use --force-retrain to override)')
                    )
                    
            except Exception as e:
                logger.error(f"Error training price predictor: {e}")
                self.stdout.write(
                    self.style.ERROR(f'Error training price predictor: {str(e)}')
                )
                results['price_predictor'] = {'status': 'error', 'message': str(e)}
        
        # Train anomaly detector (future implementation)
        if model_type in ['anomaly_detector', 'all']:
            self.stdout.write('Anomaly detector training not yet implemented...')
            results['anomaly_detector'] = {'status': 'not_implemented'}
        
        # Display summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('TRAINING SUMMARY:'))
        self.stdout.write('='*50)
        
        for model_name, result in results.items():
            status = result.get('status', 'unknown')
            if status == 'training_completed':
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {model_name}: Successfully trained')
                )
            elif status == 'model_already_trained':
                self.stdout.write(
                    self.style.WARNING(f'→ {model_name}: Already trained')
                )
            elif status == 'insufficient_data':
                self.stdout.write(
                    self.style.WARNING(f'⚠ {model_name}: Insufficient data')
                )
            elif status == 'not_implemented':
                self.stdout.write(
                    self.style.WARNING(f'→ {model_name}: Not implemented yet')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ {model_name}: {status}')
                )
        
        self.stdout.write('\nTraining completed!')
    
    def _get_stocks_with_data(self, max_stocks: int) -> list:
        """Get stocks that have sufficient historical data for training."""
        # Get stocks with recent trading activity
        recent_date = date.today() - timedelta(days=30)
        
        stocks_with_data = StockSymbol.objects.filter(
            is_active=True,
            stock_data__trading_session__date__gte=recent_date
        ).distinct()
        
        # Further filter by data availability
        valid_stocks = []
        for stock in stocks_with_data[:max_stocks * 2]:  # Check more than needed
            # Check if stock has enough historical data
            from apps.scrapers.models import StockData
            data_count = StockData.objects.filter(
                stock=stock,
                trading_session__date__gte=recent_date - timedelta(days=60)
            ).count()
            
            if data_count >= 30:  # Minimum data requirement
                valid_stocks.append(stock)
                
            if len(valid_stocks) >= max_stocks:
                break
        
        return valid_stocks
