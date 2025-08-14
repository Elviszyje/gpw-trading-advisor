"""
Management command to update test user preferences to more realistic values.
"""

from django.core.management.base import BaseCommand
from apps.users.models import User, UserTradingPreferences
from decimal import Decimal


class Command(BaseCommand):
    help = 'Update test user preferences to more realistic values for testing'

    def handle(self, *args, **options):
        """Update test user preferences."""
        
        self.stdout.write("🔧 Updating test user preferences...")
        
        try:
            # Conservative trader - more relaxed requirements
            conservative_user = User.objects.get(username='conservative_trader')
            conservative_prefs = UserTradingPreferences.objects.get(user=conservative_user)
            conservative_prefs.min_market_cap_millions = Decimal('10.0')  # 10M PLN instead of 100M
            conservative_prefs.min_daily_volume = 1000  # 1K instead of 10K
            conservative_prefs.save()
            
            # Aggressive trader - even more relaxed 
            aggressive_user = User.objects.get(username='aggressive_trader')
            aggressive_prefs = UserTradingPreferences.objects.get(user=aggressive_user)
            aggressive_prefs.min_market_cap_millions = Decimal('5.0')  # 5M PLN
            aggressive_prefs.min_daily_volume = 500  # 500 volume
            aggressive_prefs.allow_penny_stocks = True  # Allow penny stocks
            aggressive_prefs.save()
            
            # Scalper trader - focused on high liquidity, lower market cap ok
            scalper_user = User.objects.get(username='scalper_trader')
            scalper_prefs = UserTradingPreferences.objects.get(user=scalper_user)
            scalper_prefs.min_market_cap_millions = Decimal('50.0')  # 50M PLN
            scalper_prefs.min_daily_volume = 5000  # 5K volume for scalping
            scalper_prefs.save()
            
            self.stdout.write(
                self.style.SUCCESS("✅ Test user preferences updated successfully!")
            )
            
            # Display updated preferences
            for username in ['conservative_trader', 'aggressive_trader', 'scalper_trader']:
                user = User.objects.get(username=username)
                prefs = UserTradingPreferences.objects.get(user=user)
                self.stdout.write(f"\n📊 {username} updated preferences:")
                self.stdout.write(f"   - Min market cap: {prefs.min_market_cap_millions} millions PLN")
                self.stdout.write(f"   - Min daily volume: {prefs.min_daily_volume}")
                self.stdout.write(f"   - Allow penny stocks: {prefs.allow_penny_stocks}")
                self.stdout.write(f"   - Target profit: {prefs.target_profit_percentage}%")
                self.stdout.write(f"   - Max loss: {prefs.max_loss_percentage}%")
                self.stdout.write(f"   - Min confidence: {prefs.min_confidence_threshold}%")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error updating preferences: {e}")
            )
            raise
