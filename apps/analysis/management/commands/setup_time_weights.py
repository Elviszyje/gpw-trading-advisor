"""
Management command to create default time weight configurations
"""

from django.core.management.base import BaseCommand
from apps.analysis.models import TimeWeightConfiguration


class Command(BaseCommand):
    help = 'Create default time weight configurations for different trading styles'

    def handle(self, *args, **options):
        """Create default configurations"""
        
        configurations = [
            {
                'name': 'intraday_default',
                'trading_style': 'intraday',
                'half_life_minutes': 120,
                'last_15min_weight': 0.4,
                'last_1hour_weight': 0.3,
                'last_4hour_weight': 0.2,
                'today_weight': 0.1,
                'breaking_news_multiplier': 2.0,
                'market_hours_multiplier': 1.5,
                'pre_market_multiplier': 1.2,
                'min_impact_threshold': 0.05,
            },
            {
                'name': 'intraday_aggressive',
                'trading_style': 'intraday',
                'half_life_minutes': 90,
                'last_15min_weight': 0.5,
                'last_1hour_weight': 0.3,
                'last_4hour_weight': 0.15,
                'today_weight': 0.05,
                'breaking_news_multiplier': 2.5,
                'market_hours_multiplier': 1.8,
                'pre_market_multiplier': 1.4,
                'min_impact_threshold': 0.03,
            },
            {
                'name': 'intraday_conservative',
                'trading_style': 'intraday',
                'half_life_minutes': 180,
                'last_15min_weight': 0.3,
                'last_1hour_weight': 0.3,
                'last_4hour_weight': 0.25,
                'today_weight': 0.15,
                'breaking_news_multiplier': 1.5,
                'market_hours_multiplier': 1.2,
                'pre_market_multiplier': 1.1,
                'min_impact_threshold': 0.1,
            },
            {
                'name': 'swing_trading',
                'trading_style': 'swing',
                'half_life_minutes': 720,  # 12 hours
                'last_15min_weight': 0.2,
                'last_1hour_weight': 0.25,
                'last_4hour_weight': 0.3,
                'today_weight': 0.25,
                'breaking_news_multiplier': 1.8,
                'market_hours_multiplier': 1.3,
                'pre_market_multiplier': 1.15,
                'min_impact_threshold': 0.07,
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for config_data in configurations:
            config, created = TimeWeightConfiguration.objects.get_or_create(
                name=config_data['name'],
                defaults=config_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created configuration: {config.name}')
                )
            else:
                # Update existing configuration with new values
                for key, value in config_data.items():
                    if key != 'name':
                        setattr(config, key, value)
                config.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'🔄 Updated configuration: {config.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Summary: {created_count} created, {updated_count} updated'
            )
        )
        
        # Display all configurations
        self.stdout.write('\n📋 All Time Weight Configurations:')
        for config in TimeWeightConfiguration.objects.all():
            status = '✅ Active' if config.is_active else '❌ Inactive'
            self.stdout.write(f'  • {config.name} ({config.trading_style}) - {status}')
