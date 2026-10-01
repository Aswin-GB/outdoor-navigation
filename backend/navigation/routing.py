"""
WebSocket URL routing.
"""
from django.urls import re_path
from navigation.consumers import NavigationConsumer

websocket_urlpatterns = [
    re_path(r'ws/navigation/(?P<navigation_id>[0-9a-f-]+)/$', NavigationConsumer.as_asgi()),
]
