"""
Management command to test personalized trading signals.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator
from apps.users.models import UserTradingPreferences
from apps.core.models import StockSymbol, TradingSession

User = get_user_model()


class Command(BaseCommand):
    help = 'Test personalized trading signals for different user types'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--create-test-users',
            action='store_true',
            help='Create test users with different trading preferences'
        )
        parser.add_argument(
            '--generate-signals',
            action='store_true', 
            help='Generate personalized signals for test users'
        )
        parser.add_argument(
            '--use-session-date',
            type=str,
            help='Use specific session date (YYYY-MM-DD) for testing, defaults to latest available session'
        )

    def get_test_trading_session(self, session_date_str=None):
        """Get trading session for testing - either specified or latest available."""
        if session_date_str:
            try:
                session_date = datetime.strptime(session_date_str, '%Y-%m-%d').date()
                session = TradingSession.objects.get(date=session_date)
                return session
            except (ValueError, TradingSession.DoesNotExist) as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Invalid session date or session not found: {e}")
                )
                return None
        
        # Get latest session with indicator data
        from apps.analysis.models import IndicatorValue
        latest_session = TradingSession.objects.filter(
            indicator_values__isnull=False
        ).distinct().order_by('-date').first()
        
        if latest_session:
            self.stdout.write(f"📅 Using latest available session with data: {latest_session.date}")
            return latest_session
        else:
            self.stdout.write(
                self.style.ERROR("❌ No trading sessions with indicator data found!")
            )
            return None

    def handle(self, *args, **options):
        if options['create_test_users']:
            self.create_test_users()
        
        if options['generate_signals']:
            # Get test session first
            test_session = self.get_test_trading_session(options.get('use_session_date'))
            if not test_session:
                return
                
            if options.get('user_id'):
                self.test_signals_for_user(options['user_id'], test_session)
            else:
                self.test_all_users(test_session)

    def create_test_users(self):
        """Create test users with different trading preferences."""
        self.stdout.write("Creating test users with different trading preferences...")

        # Conservative Trader
        conservative_user, created = User.objects.get_or_create(
            username='conservative_trader',
            defaults={
                'email': 'conservative@test.com',
                'first_name': 'Conservative',
                'last_name': 'Trader'
            }
        )
        
        if created or not hasattr(conservative_user, 'trading_preferences'):
            conservative_prefs, _ = UserTradingPreferences.objects.get_or_create(
                user=conservative_user,
                defaults={
                    'available_capital': Decimal('50000.00'),
                    'target_profit_percentage': Decimal('2.0'),
                    'max_loss_percentage': Decimal('1.5'),
                    'min_confidence_threshold': Decimal('75.0'),
                    'max_position_size_percentage': Decimal('5.0'),
                    'trading_style': 'conservative',
                    'preferred_holding_time_hours': 8,
                    'max_holding_time_hours': 24,
                    'min_daily_volume': 50000,
                    'min_market_cap_millions': Decimal('500.0'),
                    'notification_frequency': 'daily',
                    'max_signals_per_day': 2,
                }
            )
            self.stdout.write(f"✅ Created conservative trader: {conservative_user.username}")

        # Aggressive Trader  
        aggressive_user, created = User.objects.get_or_create(
            username='aggressive_trader',
            defaults={
                'email': 'aggressive@test.com',
                'first_name': 'Aggressive',
                'last_name': 'Trader'
            }
        )
        
        if created or not hasattr(aggressive_user, 'trading_preferences'):
            aggressive_prefs, _ = UserTradingPreferences.objects.get_or_create(
                user=aggressive_user,
                defaults={
                    'available_capital': Decimal('20000.00'),
                    'target_profit_percentage': Decimal('5.0'),
                    'max_loss_percentage': Decimal('3.0'),
                    'min_confidence_threshold': Decimal('50.0'),
                    'max_position_size_percentage': Decimal('20.0'),
                    'trading_style': 'aggressive',
                    'preferred_holding_time_hours': 2,
                    'max_holding_time_hours': 6,
                    'min_daily_volume': 5000,
                    'min_market_cap_millions': Decimal('50.0'),
                    'notification_frequency': 'immediate',
                    'max_signals_per_day': 10,
                }
            )
            self.stdout.write(f"✅ Created aggressive trader: {aggressive_user.username}")

        # Scalper
        scalper_user, created = User.objects.get_or_create(
            username='scalper_trader',
            defaults={
                'email': 'scalper@test.com',
                'first_name': 'Scalper',
                'last_name': 'Trader'
            }
        )
        
        if created or not hasattr(scalper_user, 'trading_preferences'):
            scalper_prefs, _ = UserTradingPreferences.objects.get_or_create(
                user=scalper_user,
                defaults={
                    'available_capital': Decimal('100000.00'),
                    'target_profit_percentage': Decimal('1.0'),
                    'max_loss_percentage': Decimal('0.8'),
                    'min_confidence_threshold': Decimal('70.0'),
                    'max_position_size_percentage': Decimal('30.0'),
                    'trading_style': 'scalping',
                    'preferred_holding_time_hours': 1,
                    'max_holding_time_hours': 2,
                    'min_daily_volume': 100000,
                    'min_market_cap_millions': Decimal('1000.0'),
                    'notification_frequency': 'immediate',
                    'max_signals_per_day': 20,
                }
            )
            self.stdout.write(f"✅ Created scalper: {scalper_user.username}")

        self.stdout.write(self.style.SUCCESS("Test users created successfully!"))

    def test_signals_for_user(self, user_id):
        """Test personalized signals for specific user."""
        try:
            user = User.objects.get(id=user_id)
            self.stdout.write(f"\n🔍 Testing personalized signals for: {user.username}")
            
            generator = DailyTradingSignalGenerator()
            
            # Get user preferences
            try:
                preferences = getattr(user, 'trading_preferences', None)
                if not preferences:
                    preferences = UserTradingPreferences.get_default_preferences(user)
                
                self.stdout.write(f"📊 User preferences:")
                self.stdout.write(f"   - Trading style: {preferences.trading_style}")
                self.stdout.write(f"   - Capital: {preferences.available_capital} PLN")
                self.stdout.write(f"   - Target profit: {preferences.target_profit_percentage}%")
                self.stdout.write(f"   - Max loss: {preferences.max_loss_percentage}%")
                self.stdout.write(f"   - Min confidence: {preferences.min_confidence_threshold}%")
                self.stdout.write(f"   - Max position size: {preferences.max_position_size_percentage}%")
                
            except Exception as e:
                self.stdout.write(f"⚠️ Error getting preferences: {e}")
                preferences = None

            # Generate portfolio signals
            signals = generator.generate_signals_for_user_portfolio(user)
            
            self.stdout.write(f"\n📈 Generated {len(signals)} signals:")
            
            actionable_signals = 0
            for i, signal in enumerate(signals[:5], 1):  # Show first 5
                if signal['signal'] in ['BUY', 'SELL']:
                    actionable_signals += 1
                    self.stdout.write(f"\n{i}. {signal['stock']} - {signal['signal']}")
                    self.stdout.write(f"   Confidence: {signal['confidence']}%")
                    self.stdout.write(f"   Reason: {signal['reason']}")
                    
                    if 'risk_management' in signal and signal['risk_management']:
                        risk = signal['risk_management']
                        self.stdout.write(f"   💰 Position size: {risk.get('position_size_pln', 'N/A')} PLN ({risk.get('position_size_pct', 'N/A')}%)")
                        self.stdout.write(f"   📈 Take profit: {risk.get('take_profit', 'N/A')} PLN (+{risk.get('target_profit_pct', 'N/A')}%)")
                        self.stdout.write(f"   📉 Stop loss: {risk.get('stop_loss', 'N/A')} PLN (-{risk.get('max_loss_pct', 'N/A')}%)")
                        if 'target_profit_amount_pln' in risk:
                            self.stdout.write(f"   💵 Potential profit: {risk['target_profit_amount_pln']} PLN")
                            self.stdout.write(f"   💸 Potential loss: {risk['max_loss_amount_pln']} PLN")
                else:
                    self.stdout.write(f"\n{i}. {signal['stock']} - {signal['signal']} (Confidence: {signal['confidence']}%)")
                    self.stdout.write(f"   Reason: {signal['reason']}")
            
            self.stdout.write(f"\n📊 Summary: {actionable_signals} actionable signals out of {len(signals)} total")
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with ID {user_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error testing signals: {e}"))

    def test_all_users(self):
        """Test signals for all test users."""
        test_usernames = ['conservative_trader', 'aggressive_trader', 'scalper_trader']
        
        for username in test_usernames:
            try:
                user = User.objects.get(username=username)
                self.test_signals_for_user(user.id)
            except User.DoesNotExist:
                self.stdout.write(f"⚠️ Test user {username} not found. Run --create-test-users first.")

    def test_comparison(self):
        """Compare signals between different user types for same stock."""
        self.stdout.write("\n🔄 Comparing signals for same stock across different user types...")
        
        # Get a test stock
        test_stock = StockSymbol.objects.filter(is_active=True).first()
        if not test_stock:
            self.stdout.write("❌ No active stocks found")
            return
        
        generator = DailyTradingSignalGenerator()
        
        # Test with different users
        test_users = User.objects.filter(username__in=['conservative_trader', 'aggressive_trader', 'scalper_trader'])
        
        self.stdout.write(f"📊 Testing {test_stock.symbol} for different user types:")
        
        for user in test_users:
            signal = generator.generate_personalized_signals_for_user(user, test_stock)
            self.stdout.write(f"\n👤 {user.username}:")
            self.stdout.write(f"   Signal: {signal['signal']} ({signal['confidence']}%)")
            if 'risk_management' in signal and signal['risk_management']:
                risk = signal['risk_management']
                self.stdout.write(f"   Position: {risk.get('position_size_pln', 'N/A')} PLN")
                self.stdout.write(f"   Risk/Reward: {risk.get('risk_reward_ratio', 'N/A')}")
