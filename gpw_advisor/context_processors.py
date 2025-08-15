# context_processors.py
"""
Context processors for GPW Trading Advisor
"""

def ml_availability(request):
    """
    Add ML views availability to template context
    """
    try:
        from apps.analysis import ml_views
        return {'ML_VIEWS_AVAILABLE': True}
    except ImportError:
        return {'ML_VIEWS_AVAILABLE': False}
