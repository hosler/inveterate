from django.conf.urls import include
from django.urls import path
from drf_auto_endpoint.router import router

urlpatterns = [
    path('', include(router.urls)),
]
