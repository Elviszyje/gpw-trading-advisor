"""
Management command to generate personalized trading signals for users.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator
from apps.core.models import StockSymbol
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate personalized trading signals for users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to generate signals for'
        )
        parser.add_argument(
            '--stock',
            type=str,
            help='Stock symbol to analyze (optional)'
        )
        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Generate signals for all active users'
        )
        parser.add_argument(
            '--create-test-user',
            action='store_true',
            help='Create a test user with different trading preferences'
        )

    def handle(self, *args, **options):
        generator = DailyTradingSignalGenerator()
        
        if options['create_test_user']:
            self.create_test_users()
            return
        
        if options['all_users']:
            users = User.objects.filter(is_active=True)
            self.stdout.write(f"Generating signals for {users.count()} users...")
            
            for user in users:
                self.generate_signals_for_user(generator, user, options.get('stock'))
        
        elif options['user']:
            try:
                user = User.objects.get(username=options['user'])
                self.generate_signals_for_user(generator, user, options.get('stock'))
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User '{options['user']}' does not exist")
                )
        else:
            self.stdout.write(
                self.style.ERROR("Please specify --user <username> or --all-users")
            )

    def create_test_users(self):
        """Create test users with different trading preferences."""
        from apps.users.models import UserTradingPreferences
        from decimal import Decimal
        
        test_users = [
            {
                'username': 'conservative_trader',
                'email': 'conservative@test.com',
                'preferences': {
                    'trading_style': 'conservative',
                    'target_profit_percentage': Decimal('2.0'),
                    'max_loss_percentage': Decimal('1.0'),
                    'min_confidence_threshold': Decimal('75.0'),
                    'max_position_size_percentage': Decimal('5.0'),
                    'available_capital': Decimal('10000.00')
                }
            },
            {
                'username': 'aggressive_trader',
                'email': 'aggressive@test.com',
                'preferences': {
                    'trading_style': 'aggressive',
                    'target_profit_percentage': Decimal('8.0'),
                    'max_loss_percentage': Decimal('4.0'),
                    'min_confidence_threshold': Decimal('45.0'),
                    'max_position_size_percentage': Decimal('20.0'),
                    'available_capital': Decimal('50000.00')
                }
            },
            {
                'username': 'scalper_trader',
                'email': 'scalper@test.com',
                'preferences': {
                    'trading_style': 'scalping',
                    'target_profit_percentage': Decimal('1.5'),
                    'max_loss_percentage': Decimal('0.8'),
                    'min_confidence_threshold': Decimal('80.0'),
                    'max_position_size_percentage': Decimal('15.0'),
                    'available_capital': Decimal('25000.00'),
                    'preferred_holding_time_hours': 1,
                    'max_signals_per_day': 15
                }
            }
        ]
        
        for user_data in test_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(f"Created user: {user.username}")
            
            # Create or update preferences
            preferences, pref_created = UserTradingPreferences.objects.get_or_create(
                user=user,
                defaults=user_data['preferences']
            )
            
            if not pref_created:
                # Update existing preferences
                for key, value in user_data['preferences'].items():
                    setattr(preferences, key, value)
                preferences.save()
            
            self.stdout.write(f"  ✓ {user.username} - {preferences.trading_style} style")
            self.stdout.write(f"    Capital: {preferences.available_capital} PLN")
            self.stdout.write(f"    Target profit: {preferences.target_profit_percentage}%")
            self.stdout.write(f"    Max loss: {preferences.max_loss_percentage}%")
            self.stdout.write(f"    Min confidence: {preferences.min_confidence_threshold}%")
            self.stdout.write("")

    def generate_signals_for_user(self, generator, user, stock_symbol=None):
        """Generate personalized signals for a specific user."""
        self.stdout.write(f"\n=== Signals for {user.username} ===")
        
        # Get user preferences
        try:
            preferences = user.trading_preferences
            self.stdout.write(f"Trading Style: {preferences.trading_style}")
            self.stdout.write(f"Available Capital: {preferences.available_capital} PLN")
            self.stdout.write(f"Min Confidence: {preferences.min_confidence_threshold}%")
            self.stdout.write("")
        except:
            self.stdout.write("No trading preferences found - using defaults")
            preferences = None
        
        if stock_symbol:
            # Generate signal for specific stock
            try:
                stock = StockSymbol.objects.get(symbol=stock_symbol, is_active=True)
                signal = generator.generate_personalized_signals_for_user(user, stock)
                self.display_signal(signal)
            except StockSymbol.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Stock '{stock_symbol}' not found"))
        else:
            # Generate signals for user's portfolio
            signals = generator.generate_signals_for_user_portfolio(user)
            
            # Filter to only actionable signals
            actionable_signals = [
                s for s in signals 
                if s['signal'] in ['BUY', 'SELL'] and float(s.get('confidence', 0)) > 0
            ]
            
            self.stdout.write(f"Generated {len(actionable_signals)} actionable signals:")
            
            for signal in actionable_signals[:5]:  # Show top 5
                self.display_signal(signal)
    
    def display_signal(self, signal):
        """Display a signal in a formatted way."""
        stock = signal['stock']
        action = signal['signal']
        confidence = signal.get('confidence', 0)
        
        # Style the action
        if action == 'BUY':
            action_styled = self.style.SUCCESS(action)
        elif action == 'SELL':
            action_styled = self.style.WARNING(action)
        else:
            action_styled = self.style.HTTP_INFO(action)
        
        self.stdout.write(f"  📊 {stock}: {action_styled} ({confidence}% confidence)")
        
        if 'reason' in signal:
            self.stdout.write(f"      Reason: {signal['reason']}")
        
        # Display risk management info
        risk_mgmt = signal.get('risk_management', {})
        if risk_mgmt:
            self.stdout.write(f"      Entry: {risk_mgmt.get('entry_price', 'N/A')} PLN")
            self.stdout.write(f"      Stop Loss: {risk_mgmt.get('stop_loss', 'N/A')} PLN")
            self.stdout.write(f"      Take Profit: {risk_mgmt.get('take_profit', 'N/A')} PLN")
            
            if 'position_size_pln' in risk_mgmt:
                self.stdout.write(f"      Position Size: {risk_mgmt['position_size_pln']} PLN")
                self.stdout.write(f"      Max Loss: {risk_mgmt.get('max_loss_amount_pln', 'N/A')} PLN")
                self.stdout.write(f"      Target Profit: {risk_mgmt.get('target_profit_amount_pln', 'N/A')} PLN")
        
        self.stdout.write("")
