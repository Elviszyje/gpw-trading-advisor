"""
Integration module to connect trading signal generation with notification system.
This bridges the analysis engine with the notification service.
"""

import asyncio
import logging
from typing import List, Dict, Any
from django.utils import timezone
from datetime import timedelta

from apps.analysis.models import TradingSignal
from apps.notifications.enhanced_notification_service import get_enhanced_notification_service
from apps.users.models import User

logger = logging.getLogger(__name__)


class SignalNotificationIntegrator:
    """
    Integrates trading signal generation with notification delivery.
    Automatically sends notifications when new signals are generated.
    """
    
    def __init__(self):
        self.notification_service = get_enhanced_notification_service()
    
    async def process_new_signals(self, time_window_hours: int = 1) -> Dict[str, Any]:
        """
        Process and send notifications for new trading signals.
        
        Args:
            time_window_hours: Look for signals generated in the last N hours
            
        Returns:
            Dictionary with processing statistics
        """
        from asgiref.sync import sync_to_async
        
        logger.info(f"Processing new signals from the last {time_window_hours} hours...")
        
        # Get new signals that haven't been sent yet
        cutoff_time = timezone.now() - timedelta(hours=time_window_hours)
        new_signals_qs = TradingSignal.objects.filter(
            created_at__gte=cutoff_time,
            is_sent=False,
            signal_type__in=['buy', 'sell']  # Only actionable signals
        ).select_related('stock').order_by('-created_at')
        
        # Use sync_to_async for database operations
        signals_count = await sync_to_async(new_signals_qs.count)()
        new_signals = await sync_to_async(list)(new_signals_qs)
        
        stats = {
            'signals_found': signals_count,
            'signals_processed': 0,
            'notifications_sent': 0,
            'errors': 0,
            'signals': []
        }
        
        for signal in new_signals:
            try:
                # Send notifications for this signal
                notification_stats = await self.notification_service.send_trading_signal_alert(signal)
                
                # Mark signal as sent using sync_to_async
                await sync_to_async(signal.mark_as_sent)()
                
                stats['signals_processed'] += 1
                stats['notifications_sent'] += notification_stats.get('email_sent', 0) + notification_stats.get('telegram_sent', 0)
                
                signal_info = {
                    'stock': signal.stock.symbol,
                    'signal_type': signal.signal_type,
                    'confidence': float(signal.confidence),
                    'notifications': notification_stats
                }
                stats['signals'].append(signal_info)
                
                logger.info(
                    f"Processed signal {signal.stock.symbol} ({signal.signal_type}): "
                    f"Email: {notification_stats.get('email_sent', 0)}, "
                    f"Telegram: {notification_stats.get('telegram_sent', 0)}"
                )
                
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing signal {signal.pk}: {e}")
        
        logger.info(f"Signal processing complete: {stats}")
        return stats
    
    async def send_signal_notification(self, signal: TradingSignal) -> Dict[str, int]:
        """
        Send notification for a specific signal.
        
        Args:
            signal: TradingSignal instance
            
        Returns:
            Notification delivery statistics
        """
        try:
            # Get users who should receive this signal
            users = await self._get_users_for_signal(signal)
            
            if not users:
                logger.warning(f"No users configured to receive signals for {signal.stock.symbol}")
                return {'email_sent': 0, 'telegram_sent': 0, 'failed': 0}
            
            # Send notifications
            stats = await self.notification_service.send_trading_signal_alert(signal, users)
            
            # Mark as sent if successful
            if stats.get('email_sent', 0) > 0 or stats.get('telegram_sent', 0) > 0:
                from asgiref.sync import sync_to_async
                await sync_to_async(signal.mark_as_sent)()
                logger.info(f"Signal {signal.stock.symbol} marked as sent")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error sending notification for signal {signal.pk}: {e}")
            return {'email_sent': 0, 'telegram_sent': 0, 'failed': 1}
    
    async def _get_users_for_signal(self, signal: TradingSignal) -> List[User]:
        """
        Get users who should receive notifications for this signal.
        
        Args:
            signal: TradingSignal instance
            
        Returns:
            List of User instances
        """
        # For now, get all active users with notifications enabled
        # Later this can be enhanced with user watchlists, preferences, etc.
        from asgiref.sync import sync_to_async
        
        users = await sync_to_async(list)(User.objects.filter(
            is_active=True,
            email_notifications=True  # Using the direct field from User model
        ))
        
        logger.info(f"Found {len(users)} users for signal notifications")
        return users


# Global integrator instance
signal_notification_integrator = SignalNotificationIntegrator()


def get_signal_notification_integrator() -> SignalNotificationIntegrator:
    """Get the global signal notification integrator instance."""
    return signal_notification_integrator
