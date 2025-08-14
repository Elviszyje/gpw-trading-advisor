"""
Management command to create initial test data for GPW Trading Advisor.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.models import StockSymbol, TradingSession
from apps.users.models import SubscriptionPlan
from datetime import date, time


class Command(BaseCommand):
    help = 'Create initial test data for the GPW Trading Advisor'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating initial test data...'))
        
        # Create popular Polish stocks
        stocks_data = [
            {
                'symbol': 'PKN',
                'name': 'PKN Orlen',
                'sector': 'Energy',
                'stooq_url': 'https://stooq.pl/q/?s=pkn'
            },
            {
                'symbol': 'PKO',
                'name': 'Bank PKO BP',
                'sector': 'Banking',
                'stooq_url': 'https://stooq.pl/q/?s=pko'
            },
            {
                'symbol': 'CDR',
                'name': 'CD Projekt',
                'sector': 'Technology',
                'stooq_url': 'https://stooq.pl/q/?s=cdr'
            },
            {
                'symbol': 'LPP',
                'name': 'LPP',
                'sector': 'Retail',
                'stooq_url': 'https://stooq.pl/q/?s=lpp'
            },
            {
                'symbol': 'JSW',
                'name': 'Jastrzębska Spółka Węglowa',
                'sector': 'Mining',
                'stooq_url': 'https://stooq.pl/q/?s=jsw'
            },
            {
                'symbol': 'KGH',
                'name': 'KGHM Polska Miedź',
                'sector': 'Mining',
                'stooq_url': 'https://stooq.pl/q/?s=kgh'
            },
        ]
        
        created_stocks = 0
        for stock_data in stocks_data:
            stock, created = StockSymbol.objects.get_or_create(
                symbol=stock_data['symbol'],
                defaults=stock_data
            )
            if created:
                created_stocks += 1
                self.stdout.write(f'  ✓ Created stock: {stock.symbol} - {stock.name}')
            else:
                self.stdout.write(f'  → Stock already exists: {stock.symbol}')
        
        # Create subscription plans
        plans_data = [
            {
                'name': 'Free Plan',
                'plan_type': 'free',
                'price': 0.00,
                'duration_days': 365,
                'max_stocks_monitored': 3,
                'notifications_enabled': True,
                'telegram_notifications': False,
                'email_notifications': True,
                'advanced_analysis': False,
                'description': 'Basic monitoring for up to 3 stocks'
            },
            {
                'name': 'Premium Plan',
                'plan_type': 'premium',
                'price': 29.99,
                'duration_days': 30,
                'max_stocks_monitored': 15,
                'notifications_enabled': True,
                'telegram_notifications': True,
                'email_notifications': True,
                'advanced_analysis': True,
                'description': 'Advanced analysis and notifications for up to 15 stocks'
            },
            {
                'name': 'Professional Plan',
                'plan_type': 'pro',
                'price': 79.99,
                'duration_days': 30,
                'max_stocks_monitored': 50,
                'notifications_enabled': True,
                'telegram_notifications': True,
                'email_notifications': True,
                'advanced_analysis': True,
                'description': 'Professional features for serious traders'
            },
        ]
        
        created_plans = 0
        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.get_or_create(
                plan_type=plan_data['plan_type'],
                defaults=plan_data
            )
            if created:
                created_plans += 1
                self.stdout.write(f'  ✓ Created plan: {plan.name} ({plan.plan_type})')
            else:
                self.stdout.write(f'  → Plan already exists: {plan.name}')
        
        # Create current trading session
        today = date.today()
        session, created = TradingSession.objects.get_or_create(
            date=today,
            defaults={
                'is_trading_day': True,
                'market_open_time': time(9, 0),
                'market_close_time': time(17, 30),
                'notes': 'Trading session created by initial data command'
            }
        )
        
        if created:
            self.stdout.write(f'  ✓ Created trading session for {today}')
        else:
            self.stdout.write(f'  → Trading session already exists for {today}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Initial data creation complete!\n'
                f'  • Stocks created: {created_stocks}/{len(stocks_data)}\n'
                f'  • Plans created: {created_plans}/{len(plans_data)}\n'
                f'  • Trading session: {"created" if created else "exists"}'
            )
        )
