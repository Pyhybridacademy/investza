from django.urls import path
from . import views

urlpatterns = [
    path('subscribe/',   views.push_subscribe,   name='push_subscribe'),
    path('unsubscribe/', views.push_unsubscribe,  name='push_unsubscribe'),
]
