"""
Signals for user account management
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from apps.accounts.models import User, UserProfile, UserSession


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(user_logged_in)
def track_user_login(sender, request, user, **kwargs):
    """Track user login activity"""
    # Get IP address
    ip_address = get_client_ip(request)
    
    # Update user login tracking
    user.increment_login_count(ip_address)
    
    # Create or update session tracking
    session_key = request.session.session_key
    if session_key:
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Close any existing active sessions for this user
        UserSession.objects.filter(
            user=user,
            is_active=True
        ).exclude(
            session_key=session_key
        ).update(is_active=False)
        
        # Create new session record
        UserSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                'user': user,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'is_active': True
            }
        )


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
