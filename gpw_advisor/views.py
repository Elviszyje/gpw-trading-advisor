"""
Main views for GPW Trading Advisor
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse


def home_view(request: HttpRequest) -> HttpResponse:
    """
    Home page view - shows landing page for guests, redirects to dashboard for authenticated users
    """
    if request.user.is_authenticated:
        # If user is logged in, redirect to dashboard
        return redirect('users:dashboard')
    else:
        # If user is not logged in, show landing page
        context = {
            'title': 'GPW Trading Advisor',
            'description': 'Zaawansowana platforma inteligencji tradingowej dla Giełdy Papierów Wartościowych w Warszawie. Analiza techniczna, sentyment rynkowy, powiadomienia w czasie rzeczywistym.'
        }
        return render(request, 'main/landing.html', context)


@login_required
def main_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Main dashboard for authenticated users
    """
    return redirect('users:dashboard')


def about_view(request: HttpRequest) -> HttpResponse:
    """
    About page view
    """
    context = {
        'title': 'About GPW Trading Advisor',
        'description': 'Advanced trading intelligence platform for Warsaw Stock Exchange'
    }
    return render(request, 'main/about.html', context)
