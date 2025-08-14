"""
User notification preference management.
Handles user settings for different types of notifications.
"""

from django.db import models, transaction
from apps.users.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class NotificationPreferenceManager:
    """
    Manages user notification preferences and settings.
    """
    
    @staticmethod
    def get_or_create_preferences(user: User) -> Dict[str, Any]:
        """
        Get or create notification preferences for a user.
        Uses the User model's built-in notification fields.
        """
        try:
            # Return current preferences from User model
            return {
                'email_notifications': user.email_notifications,
                'sms_notifications': user.sms_notifications,
                'telegram_chat_id': user.telegram_chat_id,
                'sentiment_alert_threshold': user.sentiment_alert_threshold,
                'impact_alert_threshold': user.impact_alert_threshold,
                'dashboard_refresh_interval': user.dashboard_refresh_interval,
                'timezone_preference': user.timezone_preference,
            }
        except Exception as e:
            logger.error(f"Error getting preferences for user {user.pk}: {e}")
            return {
                'email_notifications': True,
                'sms_notifications': False,
                'telegram_chat_id': None,
                'sentiment_alert_threshold': 0.8,
                'impact_alert_threshold': 0.7,
                'dashboard_refresh_interval': 300,
                'timezone_preference': 'Europe/Warsaw',
            }
    
    @staticmethod
    def update_preferences(user: User, preferences: Dict[str, Any]) -> bool:
        """
        Update user notification preferences.
        """
        try:
            with transaction.atomic():
                # Update User model fields
                if 'email_notifications' in preferences:
                    user.email_notifications = preferences['email_notifications']
                
                if 'sms_notifications' in preferences:
                    user.sms_notifications = preferences['sms_notifications']
                
                if 'telegram_chat_id' in preferences:
                    user.telegram_chat_id = preferences['telegram_chat_id']
                
                if 'sentiment_alert_threshold' in preferences:
                    threshold = float(preferences['sentiment_alert_threshold'])
                    if 0.1 <= threshold <= 1.0:
                        user.sentiment_alert_threshold = threshold
                    else:
                        raise ValidationError("Sentiment threshold must be between 0.1 and 1.0")
                
                if 'impact_alert_threshold' in preferences:
                    threshold = float(preferences['impact_alert_threshold'])
                    if 0.1 <= threshold <= 1.0:
                        user.impact_alert_threshold = threshold
                    else:
                        raise ValidationError("Impact threshold must be between 0.1 and 1.0")
                
                if 'dashboard_refresh_interval' in preferences:
                    interval = int(preferences['dashboard_refresh_interval'])
                    if 30 <= interval <= 3600:  # 30 seconds to 1 hour
                        user.dashboard_refresh_interval = interval
                    else:
                        raise ValidationError("Refresh interval must be between 30 and 3600 seconds")
                
                if 'timezone_preference' in preferences:
                    user.timezone_preference = preferences['timezone_preference']
                
                user.save()
                logger.info(f"Updated preferences for user {user.pk}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating preferences for user {user.pk}: {e}")
            return False
    
    @staticmethod
    def get_notification_channels(user: User) -> List[str]:
        """
        Get enabled notification channels for a user.
        """
        channels = []
        
        if user.email_notifications:
            channels.append('email')
        
        if user.sms_notifications:
            channels.append('sms')
        
        if user.telegram_chat_id:
            channels.append('telegram')
        
        return channels
    
    @staticmethod
    def can_send_notification(user: User, notification_type: str) -> bool:
        """
        Check if a specific notification type can be sent to user.
        """
        # Basic check - user must have at least one channel enabled
        channels = NotificationPreferenceManager.get_notification_channels(user)
        if not channels:
            return False
        
        # Type-specific checks
        if notification_type == 'signal_alert':
            return user.email_notifications or bool(user.telegram_chat_id)
        
        elif notification_type == 'daily_summary':
            return user.email_notifications or bool(user.telegram_chat_id)
        
        elif notification_type == 'price_alert':
            return user.email_notifications or bool(user.telegram_chat_id)
        
        elif notification_type == 'news_alert':
            return user.email_notifications or bool(user.telegram_chat_id)
        
        return True
    
    @staticmethod
    def get_alert_thresholds(user: User) -> Dict[str, float]:
        """
        Get user's alert thresholds.
        """
        return {
            'sentiment_threshold': user.sentiment_alert_threshold,
            'impact_threshold': user.impact_alert_threshold,
        }
    
    @staticmethod
    def set_telegram_chat_id(user: User, chat_id: str) -> bool:
        """
        Set Telegram chat ID for a user.
        """
        try:
            user.telegram_chat_id = chat_id
            user.save(update_fields=['telegram_chat_id'])
            logger.info(f"Set Telegram chat ID for user {user.pk}")
            return True
        except Exception as e:
            logger.error(f"Error setting Telegram chat ID for user {user.pk}: {e}")
            return False
    
    @staticmethod
    def remove_telegram_chat_id(user: User) -> bool:
        """
        Remove Telegram chat ID for a user.
        """
        try:
            user.telegram_chat_id = None
            user.save(update_fields=['telegram_chat_id'])
            logger.info(f"Removed Telegram chat ID for user {user.pk}")
            return True
        except Exception as e:
            logger.error(f"Error removing Telegram chat ID for user {user.pk}: {e}")
            return False
    
    @staticmethod
    def get_users_for_broadcast(notification_type: str) -> List[User]:
        """
        Get list of users who should receive a specific notification type.
        """
        try:
            users = User.objects.filter(is_active=True)
            
            if notification_type == 'signal_alert':
                users = users.filter(
                    models.Q(email_notifications=True) | 
                    models.Q(telegram_chat_id__isnull=False)
                )
            
            elif notification_type == 'daily_summary':
                users = users.filter(
                    models.Q(email_notifications=True) | 
                    models.Q(telegram_chat_id__isnull=False)
                )
            
            elif notification_type == 'price_alert':
                users = users.filter(
                    models.Q(email_notifications=True) | 
                    models.Q(telegram_chat_id__isnull=False)
                )
            
            return list(users)
            
        except Exception as e:
            logger.error(f"Error getting users for broadcast {notification_type}: {e}")
            return []
    
    @staticmethod
    def get_preference_summary(user: User) -> Dict[str, Any]:
        """
        Get a summary of user's notification preferences.
        """
        channels = NotificationPreferenceManager.get_notification_channels(user)
        thresholds = NotificationPreferenceManager.get_alert_thresholds(user)
        
        return {
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
            'enabled_channels': channels,
            'total_channels': len(channels),
            'email_enabled': user.email_notifications,
            'sms_enabled': user.sms_notifications,
            'telegram_enabled': bool(user.telegram_chat_id),
            'telegram_chat_id': user.telegram_chat_id,
            'sentiment_threshold': thresholds['sentiment_threshold'],
            'impact_threshold': thresholds['impact_threshold'],
            'refresh_interval': user.dashboard_refresh_interval,
            'timezone': user.timezone_preference,
            'can_receive_signals': NotificationPreferenceManager.can_send_notification(user, 'signal_alert'),
            'can_receive_summaries': NotificationPreferenceManager.can_send_notification(user, 'daily_summary'),
            'can_receive_price_alerts': NotificationPreferenceManager.can_send_notification(user, 'price_alert'),
        }


# Quick access functions
def get_user_preferences(user: User) -> Dict[str, Any]:
    """Quick function to get user preferences."""
    return NotificationPreferenceManager.get_or_create_preferences(user)


def update_user_preferences(user: User, preferences: Dict[str, Any]) -> bool:
    """Quick function to update user preferences."""
    return NotificationPreferenceManager.update_preferences(user, preferences)


def can_notify_user(user: User, notification_type: str) -> bool:
    """Quick function to check if user can receive notification."""
    return NotificationPreferenceManager.can_send_notification(user, notification_type)
