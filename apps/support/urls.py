from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.user_chat_view, name='user_chat'),
]

admin_urlpatterns = [
    path('chat/',                            views.admin_chat_inbox,   name='admin_chat_inbox'),
    path('chat/<uuid:session_id>/',          views.admin_chat_session, name='admin_chat_session'),
    path('chat/<uuid:session_id>/close/',    views.admin_close_session, name='admin_close_session'),
]
