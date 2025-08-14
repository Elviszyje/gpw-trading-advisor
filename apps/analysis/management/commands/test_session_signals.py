"""
Simplified test to validate personalized signals with specific trading session.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator
from apps.core.models import StockSymbol, TradingSession
from apps.users.models import UserTradingPreferences
from datetime import datetime

User = get_user_model()


class Command(BaseCommand):
    help = 'Test personalized signals with specific trading session'

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-date',
            type=str,
            help='Session date (YYYY-MM-DD), defaults to latest available'
        )

    def handle(self, *args, **options):
        """Test personalized signals with specific session."""
        
        # Get test session
        test_session = self.get_test_session(options.get('session_date'))
        if not test_session:
            return
        
        self.stdout.write(f"🎯 Testing with session: {test_session.date}")
        
        # Test with our users
        usernames = ['conservative_trader', 'aggressive_trader', 'scalper_trader']
        
        for username in usernames:
            try:
                user = User.objects.get(username=username)
                self.test_user_with_session(user, test_session)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"⚠️ User {username} not found - run with --create-test-users first")
                )

    def get_test_session(self, session_date_str=None):
        """Get session for testing."""
        if session_date_str:
            try:
                session_date = datetime.strptime(session_date_str, '%Y-%m-%d').date()
                session = TradingSession.objects.get(date=session_date)
                return session
            except (ValueError, TradingSession.DoesNotExist) as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Invalid session date: {e}")
                )
                return None
        
        # Get latest session with indicator data
        from apps.analysis.models import IndicatorValue
        latest_session = TradingSession.objects.filter(
            indicator_values__isnull=False
        ).distinct().order_by('-date').first()
        
        if latest_session:
            self.stdout.write(f"📅 Using latest session with data: {latest_session.date}")
            return latest_session
        else:
            self.stdout.write(
                self.style.ERROR("❌ No sessions with indicator data found!")
            )
            return None

    def test_user_with_session(self, user, test_session):
        """Test specific user with specific session."""
        self.stdout.write(f"\n🔍 Testing personalized signals for: {user.username}")
        
        # Get user preferences
        try:
            preferences = UserTradingPreferences.objects.get(user=user)
            self.stdout.write(f"📊 User preferences:")
            self.stdout.write(f"   - Trading style: {preferences.trading_style}")
            self.stdout.write(f"   - Capital: {preferences.available_capital} PLN")
            self.stdout.write(f"   - Target profit: {preferences.target_profit_percentage}%")
            self.stdout.write(f"   - Max loss: {preferences.max_loss_percentage}%")
            self.stdout.write(f"   - Min confidence: {preferences.min_confidence_threshold}%")
            self.stdout.write(f"   - Max position size: {preferences.max_position_size_percentage}%")
        except UserTradingPreferences.DoesNotExist:
            self.stdout.write(f"⚠️ No preferences found for {user.username}")
            return
        
        # Get stocks that have indicators in this session
        stocks_with_indicators = StockSymbol.objects.filter(
            indicator_values__trading_session=test_session
        ).distinct()[:10]  # Limit to 10 for testing
        
        if not stocks_with_indicators.exists():
            self.stdout.write(f"❌ No stocks with indicators found for session {test_session.date}")
            return
        
        self.stdout.write(f"📈 Testing {stocks_with_indicators.count()} stocks with indicators:")
        
        generator = DailyTradingSignalGenerator()
        actionable_signals = 0
        total_signals = 0
        
        for stock in stocks_with_indicators:
            # Generate personalized signal for this specific session
            signal = generator.generate_personalized_signals_for_user(
                user, stock, test_session
            )
            total_signals += 1
            
            if signal['signal'] in ['BUY', 'SELL']:
                actionable_signals += 1
                self.stdout.write(f"\n✅ {signal['stock']} - {signal['signal']}")
                self.stdout.write(f"   Confidence: {signal['confidence']}%")
                self.stdout.write(f"   Reason: {signal.get('reason', 'Signal generated')}")
                
                # Show risk management if available
                if 'risk_management' in signal:
                    risk = signal['risk_management']
                    if isinstance(risk, dict) and risk:
                        self.stdout.write(f"   💰 Position size: {risk.get('position_size_pln', 'N/A')} PLN")
                        self.stdout.write(f"   📈 Take profit: +{risk.get('target_profit_pct', 'N/A')}%")
                        self.stdout.write(f"   📉 Stop loss: -{risk.get('max_loss_pct', 'N/A')}%")
            elif signal['confidence'] > 0:  # Show near-miss signals
                self.stdout.write(f"\n🔶 {signal['stock']} - {signal['signal']} (Confidence: {signal['confidence']}%)")
                self.stdout.write(f"   Reason: {signal.get('reason', 'Low confidence')}")
            # Skip showing signals with 0% confidence to reduce noise
        
        self.stdout.write(f"\n📊 Summary: {actionable_signals} actionable signals out of {total_signals} total")
        
        # Show personalization differences
        percentage_actionable = (actionable_signals / total_signals * 100) if total_signals > 0 else 0
        self.stdout.write(f"📈 Actionability rate: {percentage_actionable:.1f}%")
