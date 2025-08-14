"""
URL configuration for gpw_advisor project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from . import views
from apps.core.health_views import health_check, liveness_check, readiness_check

urlpatterns = [
    # Health checks (important for Docker/Kubernetes)
    path("health/", health_check, name='health_check'),
    path("health/live/", liveness_check, name='liveness_check'),
    path("health/ready/", readiness_check, name='readiness_check'),
    
    # Main application routes
    path("", views.home_view, name='home'),
    path("dashboard/", views.main_dashboard, name='main_dashboard'),
    path("admin/", admin.site.urls),
    path("users/", include('apps.users.urls')),
    path("analysis/", include('apps.analysis.urls')),
    path("api/analytics/", include('apps.core.urls.analytics_urls')),
]
