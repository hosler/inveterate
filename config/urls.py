"""
Root URL configuration for Inveterate project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from inveterate import views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # Web Interface
    path('', views.home_view, name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('services/', views.ServiceListView.as_view(), name='services'),
    path('services/<int:service_id>/', views.ServiceDetailView.as_view(), name='service-detail'),
    path('services/<int:service_id>/console/', views.ServiceConsoleView.as_view(), name='service-console'),
    path('services/<int:service_id>/console/auth/', views.console_auth_view, name='console-auth'),
    path('services/<int:service_id>/console/proxy/', views.console_proxy_view, name='console-proxy'),
    path('clusters/', views.ClusterListView.as_view(), name='clusters'),
    path('nodes/', views.NodeListView.as_view(), name='nodes'),

    # REST API
    path('api/', include('inveterate.urls')),
]

# Add Stripe webhook endpoints if configured
if hasattr(settings, 'STRIPE_LIVE_SECRET_KEY') or hasattr(settings, 'STRIPE_TEST_SECRET_KEY'):
    if settings.STRIPE_LIVE_SECRET_KEY or settings.STRIPE_TEST_SECRET_KEY:
        urlpatterns.append(path('stripe/', include('djstripe.urls', namespace='djstripe')))

# Serve static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
