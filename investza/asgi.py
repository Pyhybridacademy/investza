"""
InvestZA ASGI Configuration
Handles both HTTP (Django) and WebSocket (Channels) connections.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investza.settings')

# Must call get_asgi_application() before importing anything that touches Django models
django_asgi_app = get_asgi_application()

from apps.support.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
