"""
Root URL configuration for Inveterate project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


class TokenAuthThrottle(ScopedRateThrottle):
    scope = 'token_auth'


class ThrottledObtainAuthToken(ObtainAuthToken):
    throttle_classes = [TokenAuthThrottle]

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Web Interface (app-owned)
    path('', include('inveterate.urls_web')),

    # API Token Auth
    path('api/v1/auth/token/', ThrottledObtainAuthToken.as_view(), name='api-token-auth'),

    # API Schema & Docs
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # REST API (app-owned)
    path('api/v1/', include('inveterate.urls')),

    # Backward-compat redirect
    path('api/', RedirectView.as_view(url='/api/v1/', permanent=False)),
]

# Serve static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
