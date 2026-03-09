from django.urls import path
from apps.accounts import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('bank-accounts/', views.bank_accounts, name='bank_accounts'),
    path('bank-accounts/delete/<int:pk>/', views.delete_bank_account, name='delete_bank_account'),
    path('kyc/', views.kyc_verification, name='kyc_verification'),
    path('transactions/', views.transaction_history, name='transaction_history'),
]
