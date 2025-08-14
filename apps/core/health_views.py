"""
Health check views for monitoring application status
"""
from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache
from django.conf import settings
import redis
import json
from datetime import datetime


def health_check(request):
    """
    Comprehensive health check endpoint
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': getattr(settings, 'VERSION', '1.0.0'),
        'checks': {}
    }
    
    # Check database connectivity
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        health_status['checks']['database'] = 'healthy'
    except Exception as e:
        health_status['checks']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check Redis connectivity
    try:
        cache.set('health_check', 'test', 10)
        test_value = cache.get('health_check')
        if test_value == 'test':
            health_status['checks']['cache'] = 'healthy'
        else:
            health_status['checks']['cache'] = 'unhealthy: cache test failed'
            health_status['status'] = 'unhealthy'
    except Exception as e:
        health_status['checks']['cache'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check Celery worker (optional - don't fail health check if unavailable)
    try:
        from django_celery_beat.models import PeriodicTask
        task_count = PeriodicTask.objects.count()
        health_status['checks']['celery'] = f'scheduler configured with {task_count} tasks'
    except Exception as e:
        health_status['checks']['celery'] = f'unavailable: {str(e)}'
    
    # Return appropriate status code
    status_code = 200 if health_status['status'] == 'healthy' else 503
    
    return JsonResponse(health_status, status=status_code)


def liveness_check(request):
    """
    Simple liveness check - just confirms the application is running
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': datetime.now().isoformat()
    })


def readiness_check(request):
    """
    Readiness check - confirms the application is ready to serve requests
    """
    ready = True
    checks = {}
    
    # Check database
    try:
        from django.db import connection
        connection.ensure_connection()
        checks['database'] = 'ready'
    except Exception as e:
        checks['database'] = f'not ready: {str(e)}'
        ready = False
    
    # Check cache
    try:
        cache.get('test')
        checks['cache'] = 'ready'
    except Exception as e:
        checks['cache'] = f'not ready: {str(e)}'
        ready = False
    
    status = 'ready' if ready else 'not ready'
    status_code = 200 if ready else 503
    
    return JsonResponse({
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'checks': checks
    }, status=status_code)
