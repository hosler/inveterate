"""
Root URL configuration for Inveterate project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.throttling import ScopedRateThrottle
from inveterate import views


class TokenAuthThrottle(ScopedRateThrottle):
    scope = 'token_auth'


class ThrottledObtainAuthToken(ObtainAuthToken):
    throttle_classes = [TokenAuthThrottle]

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
    path('services/order/', views.ServiceOrderView.as_view(), name='service-order'),
    path('services/<int:service_id>/', views.ServiceDetailView.as_view(), name='service-detail'),
    path('services/<int:service_id>/console/', views.ServiceConsoleView.as_view(), name='service-console'),
    path('services/<int:service_id>/console/auth/', views.console_auth_view, name='console-auth'),
    path('services/<int:service_id>/console/proxy/', views.console_proxy_view, name='console-proxy'),
    path('clusters/', views.ClusterListView.as_view(), name='clusters'),
    path('nodes/', views.NodeListView.as_view(), name='nodes'),
    path('dashboard/services/', views.AdminServiceListView.as_view(), name='admin-services'),
    path('dashboard/plans/', views.PlanListView.as_view(), name='admin-plans'),
    path('dashboard/templates/', views.TemplateListView.as_view(), name='admin-templates'),
    path('dashboard/apps/', views.AppProfileListView.as_view(), name='admin-apps'),
    path('dashboard/ips/', views.IPPoolListView.as_view(), name='admin-ips'),

    # API Token Auth
    path('api/auth/token/', ThrottledObtainAuthToken.as_view(), name='api-token-auth'),

    # REST API
    path('api/', include('inveterate.urls')),
]

# Serve static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
