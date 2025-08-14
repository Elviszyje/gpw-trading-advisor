"""
Test personalized signals during market hours simulation.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.analysis.daily_trading_signals import DailyTradingSignalGenerator
from apps.core.models import StockSymbol, TradingSession
from apps.users.models import UserTradingPreferences
from datetime import datetime, time
from unittest.mock import patch

User = get_user_model()


class Command(BaseCommand):
    help = 'Test personalized signals with simulated market hours'

    def handle(self, *args, **options):
        """Test personalized signals during market hours."""
        
        # Get test session with data
        from apps.analysis.models import IndicatorValue
        test_session = TradingSession.objects.filter(
            indicator_values__isnull=False
        ).distinct().order_by('-date').first()
        
        if not test_session:
            self.stdout.write(self.style.ERROR("❌ No sessions with data found!"))
            return
        
        self.stdout.write(f"🎯 Testing with session: {test_session.date}")
        self.stdout.write(f"🕙 Simulating market hours (10:00 AM)")
        
        # Get stocks with indicators
        stocks_with_indicators = StockSymbol.objects.filter(
            indicator_values__trading_session=test_session
        ).distinct()[:3]  # Test with 3 stocks
        
        usernames = ['conservative_trader', 'aggressive_trader', 'scalper_trader']
        
        # Simulate market hours (10:00 AM)
        market_time = time(10, 0)
        
        for username in usernames:
            try:
                user = User.objects.get(username=username)
                self.test_user_during_market_hours(user, test_session, stocks_with_indicators, market_time)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"⚠️ User {username} not found")
                )

    def test_user_during_market_hours(self, user, test_session, stocks, market_time):
        """Test user with simulated market hours."""
        self.stdout.write(f"\n🔍 Testing: {user.username}")
        
        # Get preferences
        try:
            preferences = UserTradingPreferences.objects.get(user=user)
            self.stdout.write(f"📊 Profile: {preferences.trading_style} | "
                            f"Capital: {preferences.available_capital} PLN | "
                            f"Min confidence: {preferences.min_confidence_threshold}%")
        except UserTradingPreferences.DoesNotExist:
            self.stdout.write(f"⚠️ No preferences for {user.username}")
            return
        
        generator = DailyTradingSignalGenerator()
        actionable_signals = 0
        
        for stock in stocks:
            # Mock timezone.localtime() to return our simulated time
            mock_datetime = datetime.combine(test_session.date, market_time)
            
            with patch('django.utils.timezone.localtime') as mock_localtime:
                mock_localtime.return_value = mock_datetime
                
                signal = generator.generate_personalized_signals_for_user(
                    user, stock, test_session
                )
            
            if signal['signal'] in ['BUY', 'SELL']:
                actionable_signals += 1
                self.stdout.write(f"✅ {signal['stock']} - {signal['signal']}")
                self.stdout.write(f"   💡 Confidence: {signal['confidence']}%")
                self.stdout.write(f"   📝 Reason: {signal.get('reason', 'Signal generated')}")
                
                # Show personalized risk management
                if 'risk_management' in signal and signal['risk_management']:
                    risk = signal['risk_management']
                    self.stdout.write(f"   💰 Position: {risk.get('position_size_pln', 'N/A')} PLN ({risk.get('position_size_pct', 'N/A')}%)")
                    self.stdout.write(f"   📈 Target: +{risk.get('target_profit_pct', 'N/A')}% = {risk.get('take_profit', 'N/A')} PLN")
                    self.stdout.write(f"   📉 Stop: -{risk.get('max_loss_pct', 'N/A')}% = {risk.get('stop_loss', 'N/A')} PLN")
                    
                    if 'target_profit_amount_pln' in risk:
                        self.stdout.write(f"   🎯 Potential profit: {risk['target_profit_amount_pln']} PLN")
                        self.stdout.write(f"   ⚠️ Potential loss: {risk['max_loss_amount_pln']} PLN")
                
            elif signal['confidence'] > 0:
                self.stdout.write(f"🔶 {signal['stock']} - {signal['signal']} ({signal['confidence']}%)")
                self.stdout.write(f"   📝 {signal.get('reason', 'Below threshold')}")
        
        self.stdout.write(f"📊 Result: {actionable_signals} actionable signals")
        
        # Show personalization impact
        if actionable_signals > 0:
            self.stdout.write(f"🎯 Personalization: Signals customized for {preferences.trading_style} style")
        else:
            self.stdout.write(f"🛡️ Personalization: High standards ({preferences.min_confidence_threshold}% min confidence) filtered all signals")
