from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # User connects to their own chat
    re_path(r'^ws/support/user/$', consumers.UserChatConsumer.as_asgi()),

    # Admin connects to a specific session
    re_path(r'^ws/support/admin/(?P<session_id>[0-9a-f-]+)/$', consumers.AdminChatConsumer.as_asgi()),

    # Admin inbox (global — for badge counts without watching a session)
    re_path(r'^ws/support/inbox/$', consumers.AdminInboxConsumer.as_asgi()),
]
