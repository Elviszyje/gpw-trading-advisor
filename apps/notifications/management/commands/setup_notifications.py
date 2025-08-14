"""
Setup and test GPW Trading Advisor notification system.
This command sets up everything needed for daily signal notifications.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from apps.users.models import User
from telegram import Bot
import asyncio


class Command(BaseCommand):
    help = 'Setup and test the complete notification system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-telegram',
            action='store_true',
            help='Send a test Telegram message',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔧 GPW Trading Advisor - Notification System Setup')
        )
        
        # Step 1: Check configuration
        self._check_configuration()
        
        # Step 2: Setup users
        self._setup_users()
        
        # Step 3: Test Telegram if requested
        if options.get('test_telegram'):
            asyncio.run(self._test_telegram())
        
        # Step 4: Show next steps
        self._show_next_steps()

    def _check_configuration(self):
        """Check system configuration."""
        self.stdout.write("\n📋 Checking Configuration...")
        
        # Check Telegram token
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if token:
            self.stdout.write("   ✅ Telegram bot token configured")
        else:
            self.stdout.write(self.style.ERROR("   ❌ Telegram bot token missing"))
            return False
            
        # Check email settings
        email_backend = getattr(settings, 'EMAIL_BACKEND', None)
        if email_backend:
            self.stdout.write("   ✅ Email backend configured")
        else:
            self.stdout.write(self.style.WARNING("   ⚠️  Email backend not configured"))
        
        return True

    def _setup_users(self):
        """Setup users for notifications."""
        self.stdout.write("\n👥 Setting up users...")
        
        # Find user with telegram chat ID
        user = User.objects.filter(telegram_chat_id='7676229144').first()
        
        if user:
            self.stdout.write(f"   ✅ Found user: {user.email}")
            
            # Ensure email notifications are enabled
            if not getattr(user, 'email_notifications', True):
                user.email_notifications = True
                user.save()
                self.stdout.write("   ✅ Enabled email notifications")
            
            self.stdout.write(f"   📱 Telegram chat ID: {user.telegram_chat_id}")
        else:
            self.stdout.write(self.style.ERROR("   ❌ No user found with Telegram chat ID"))

    async def _test_telegram(self):
        """Test Telegram bot connection."""
        self.stdout.write("\n📱 Testing Telegram...")
        
        try:
            token = settings.TELEGRAM_BOT_TOKEN
            bot = Bot(token=token)
            
            # Test bot info
            me = await bot.get_me()
            self.stdout.write(f"   ✅ Bot: @{me.username}")
            
            # Send test message
            chat_id = '7676229144'
            message = "🧪 GPW Trading Advisor Setup Test\n\nNotification system is ready!"
            
            result = await bot.send_message(chat_id=chat_id, text=message)
            self.stdout.write(f"   ✅ Test message sent (ID: {result.message_id})")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Telegram test failed: {e}"))

    def _show_next_steps(self):
        """Show next steps for automation."""
        self.stdout.write("\n🚀 Next Steps for Automation:")
        self.stdout.write("="*50)
        
        self.stdout.write("\n1. Manual testing:")
        self.stdout.write("   python manage.py setup_notifications --test-telegram")
        
        self.stdout.write("\n2. Generate test signals and notifications:")
        self.stdout.write("   python manage.py generate_and_notify --force-generate")
        
        self.stdout.write("\n3. Daily workflow (add to crontab):")
        self.stdout.write("   0 9 * * 1-5 /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2/scripts/daily_workflow.sh")
        
        self.stdout.write("\n4. Real-time signal generation:")
        self.stdout.write("   */30 9-17 * * 1-5 cd /Users/bartoszkolek/Desktop/cloud/Projekty/GPW2 && python manage.py calculate_indicators && python manage.py generate_daily_signals --all-monitored && python manage.py generate_and_notify")
        
        self.stdout.write("\n📊 Monitor with:")
        self.stdout.write("   python manage.py monitor_notifications")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Setup complete! Check your Telegram for test message."))
