from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/<uuid:pk>/', views.admin_user_detail, name='admin_user_detail'),
    path('deposits/', views.admin_deposits, name='admin_deposits'),
    path('deposits/bank/<uuid:pk>/', views.admin_approve_bank_deposit, name='admin_approve_bank_deposit'),
    path('deposits/crypto/<uuid:pk>/', views.admin_approve_crypto_deposit, name='admin_approve_crypto_deposit'),
    path('withdrawals/', views.admin_withdrawals, name='admin_withdrawals'),
    path('withdrawals/<uuid:pk>/', views.admin_process_withdrawal, name='admin_process_withdrawal'),
    path('investments/', views.admin_investments, name='admin_investments'),
    path('plans/', views.admin_investment_plans, name='admin_investment_plans'),
    path('platform-accounts/', views.admin_platform_accounts, name='admin_platform_accounts'),
    path('reports/', views.admin_reports, name='admin_reports'),
]

# Withdrawal code management
from . import views as admin_views
urlpatterns += [
    path('withdrawal-codes/',                        admin_views.withdrawal_codes,        name='admin_withdrawal_codes'),
    path('withdrawal-codes/generate/',               admin_views.generate_withdrawal_code, name='admin_generate_withdrawal_code'),
    path('withdrawal-codes/<uuid:pk>/revoke/',       admin_views.revoke_withdrawal_code,  name='admin_revoke_withdrawal_code'),
]
