from django.urls import path
from apps.accounts import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Password reset flow
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/sent/', views.password_reset_sent, name='password_reset_sent'),
    path('password-reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/complete/', views.password_reset_complete, name='password_reset_complete'),

    # Change password (logged-in users)
    path('password-change/', views.password_change, name='password_change'),
]
