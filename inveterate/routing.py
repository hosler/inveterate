"""
WebSocket URL routing for Inveterate.
"""
try:
    from django.urls import re_path
    from . import consumers

    websocket_urlpatterns = [
        re_path(r'ws/console/(?P<service_id>\d+)/$', consumers.ConsoleProxyConsumer.as_asgi()),
    ]
except ImportError:
    websocket_urlpatterns = []
