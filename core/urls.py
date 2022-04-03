from django.conf.urls import include
from django.urls import path
from drf_auto_endpoint.router import router


def trigger_error(request):
    division_by_zero = 1 / 0


urlpatterns = [
    path("api/", include(router.urls)),
    path('api/sentry-debug/', trigger_error),
]
