"""
Telegram bot setup and management command.
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

from apps.users.models import User
from apps.notifications.preference_manager import NotificationPreferenceManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage Telegram bot for notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--setup-bot',
            action='store_true',
            help='Set up and test Telegram bot connection'
        )
        parser.add_argument(
            '--run-bot',
            action='store_true',
            help='Run Telegram bot to handle user registrations'
        )
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Test Telegram bot connection'
        )
        parser.add_argument(
            '--get-bot-info',
            action='store_true',
            help='Get Telegram bot information'
        )

    def handle(self, *args, **options):
        if options['setup_bot']:
            asyncio.run(self._setup_bot())
        
        if options['run_bot']:
            asyncio.run(self._run_bot())
        
        if options['test_connection']:
            asyncio.run(self._test_connection())
        
        if options['get_bot_info']:
            asyncio.run(self._get_bot_info())
        
        if not any([
            options['setup_bot'],
            options['run_bot'],
            options['test_connection'],
            options['get_bot_info']
        ]):
            self.stdout.write(
                self.style.WARNING('No action specified. Use --help to see available options.')
            )

    async def _setup_bot(self):
        """Set up Telegram bot."""
        self.stdout.write('Setting up Telegram bot...')
        
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not telegram_token:
            self.stdout.write(
                self.style.ERROR(
                    'TELEGRAM_BOT_TOKEN not found in settings. Please add it to your .env file:\n'
                    'TELEGRAM_BOT_TOKEN=your_bot_token_here\n\n'
                    'To get a bot token:\n'
                    '1. Message @BotFather on Telegram\n'
                    '2. Send /newbot\n'
                    '3. Follow the instructions to create your bot\n'
                    '4. Copy the token to your .env file'
                )
            )
            return
        
        try:
            bot = Bot(token=telegram_token)
            bot_info = await bot.get_me()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Bot setup successful!\n"
                    f"Bot Name: {bot_info.first_name}\n"
                    f"Bot Username: @{bot_info.username}\n"
                    f"Bot ID: {bot_info.id}\n\n"
                    f"Users can now start a conversation with @{bot_info.username} "
                    f"and use /start to register for notifications."
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Bot setup failed: {e}")
            )

    async def _test_connection(self):
        """Test Telegram bot connection."""
        self.stdout.write('Testing Telegram bot connection...')
        
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not telegram_token:
            self.stdout.write(
                self.style.ERROR('TELEGRAM_BOT_TOKEN not configured')
            )
            return
        
        try:
            bot = Bot(token=telegram_token)
            bot_info = await bot.get_me()
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Connection successful! Bot: @{bot_info.username}")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Connection failed: {e}")
            )

    async def _get_bot_info(self):
        """Get Telegram bot information."""
        self.stdout.write('Getting Telegram bot information...')
        
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not telegram_token:
            self.stdout.write(
                self.style.ERROR('TELEGRAM_BOT_TOKEN not configured')
            )
            return
        
        try:
            bot = Bot(token=telegram_token)
            bot_info = await bot.get_me()
            
            self.stdout.write(f"\n🤖 Bot Information:")
            self.stdout.write(f"Name: {bot_info.first_name}")
            self.stdout.write(f"Username: @{bot_info.username}")
            self.stdout.write(f"ID: {bot_info.id}")
            self.stdout.write(f"Can Join Groups: {bot_info.can_join_groups}")
            self.stdout.write(f"Can Read All Group Messages: {bot_info.can_read_all_group_messages}")
            self.stdout.write(f"Supports Inline Queries: {bot_info.supports_inline_queries}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error getting bot info: {e}")
            )

    async def _run_bot(self):
        """Run Telegram bot to handle user interactions."""
        self.stdout.write('Starting Telegram bot...')
        
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not telegram_token:
            self.stdout.write(
                self.style.ERROR('TELEGRAM_BOT_TOKEN not configured')
            )
            return
        
        try:
            # Create application
            application = Application.builder().token(telegram_token).build()
            
            # Add handlers
            application.add_handler(CommandHandler("start", self._handle_start))
            application.add_handler(CommandHandler("stop", self._handle_stop))
            application.add_handler(CommandHandler("status", self._handle_status))
            application.add_handler(CommandHandler("help", self._handle_help))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            
            self.stdout.write(
                self.style.SUCCESS("✅ Bot started! Press Ctrl+C to stop.")
            )
            
            # Run the bot
            await application.run_polling()
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("Bot stopped by user.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error running bot: {e}")
            )

    async def _handle_start(self, update: Update, context):
        """Handle /start command."""
        try:
            chat_id = str(update.effective_chat.id)
            user_data = update.effective_user
            
            # Welcome message
            welcome_text = (
                f"🎯 Welcome to GPW Trading Advisor!\n\n"
                f"I'm here to send you trading signals and market updates.\n\n"
                f"To receive notifications:\n"
                f"1. Log in to your account on our website\n"
                f"2. Go to notification settings\n"
                f"3. Enter this chat ID: `{chat_id}`\n\n"
                f"Available commands:\n"
                f"/start - Start receiving notifications\n"
                f"/stop - Stop notifications\n"
                f"/status - Check your notification status\n"
                f"/help - Show this help message\n\n"
                f"Happy trading! 📈"
            )
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"New user started bot: {user_data.username} (ID: {chat_id})")
            
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again later."
            )

    async def _handle_stop(self, update: Update, context):
        """Handle /stop command."""
        try:
            chat_id = str(update.effective_chat.id)
            
            # Try to find user and remove chat ID
            try:
                user = User.objects.get(telegram_chat_id=chat_id)
                user.telegram_chat_id = None
                user.save()
                
                await update.message.reply_text(
                    "✅ You have been unsubscribed from notifications.\n"
                    "Use /start to resubscribe anytime."
                )
                
                logger.info(f"User unsubscribed: {user.username} (ID: {chat_id})")
                
            except User.DoesNotExist:
                await update.message.reply_text(
                    "You are not currently subscribed to notifications.\n"
                    "Use /start to subscribe."
                )
            
        except Exception as e:
            logger.error(f"Error in stop handler: {e}")
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again later."
            )

    async def _handle_status(self, update: Update, context):
        """Handle /status command."""
        try:
            chat_id = str(update.effective_chat.id)
            
            try:
                user = User.objects.get(telegram_chat_id=chat_id)
                
                status_text = (
                    f"📊 Your Notification Status:\n\n"
                    f"✅ Connected to account: {user.username}\n"
                    f"📧 Email: {user.email}\n"
                    f"🔔 Telegram notifications: Enabled\n"
                    f"📱 Chat ID: `{chat_id}`\n\n"
                    f"You are receiving trading notifications!"
                )
                
                await update.message.reply_text(
                    status_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
            except User.DoesNotExist:
                await update.message.reply_text(
                    f"❌ Your chat ID `{chat_id}` is not linked to any account.\n\n"
                    f"To connect:\n"
                    f"1. Log in to your account\n"
                    f"2. Go to notification settings\n"
                    f"3. Enter this chat ID: `{chat_id}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"Error in status handler: {e}")
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again later."
            )

    async def _handle_help(self, update: Update, context):
        """Handle /help command."""
        help_text = (
            f"🤖 GPW Trading Advisor Bot Help\n\n"
            f"Available commands:\n"
            f"/start - Subscribe to notifications\n"
            f"/stop - Unsubscribe from notifications\n"
            f"/status - Check your notification status\n"
            f"/help - Show this help message\n\n"
            f"To link this bot to your account:\n"
            f"1. Log in to your account on our website\n"
            f"2. Go to Settings → Notifications\n"
            f"3. Enter your chat ID from /status command\n\n"
            f"For support, contact our team through the website."
        )
        
        await update.message.reply_text(help_text)

    async def _handle_message(self, update: Update, context):
        """Handle regular text messages."""
        await update.message.reply_text(
            "I don't understand that command. Use /help to see available commands."
        )
