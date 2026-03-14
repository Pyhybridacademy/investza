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
    path('profile/',                                 admin_views.admin_profile,           name='admin_profile'),
    path('withdrawal-codes/',                        admin_views.withdrawal_codes,        name='admin_withdrawal_codes'),
    path('withdrawal-codes/generate/',               admin_views.generate_withdrawal_code, name='admin_generate_withdrawal_code'),
    path('withdrawal-codes/<uuid:pk>/revoke/',       admin_views.revoke_withdrawal_code,  name='admin_revoke_withdrawal_code'),
]

# Crypto wallet management
urlpatterns += [
    path('crypto-wallets/',                              admin_views.admin_crypto_wallets,        name='admin_crypto_wallets'),
    path('crypto-wallets/add/',                          admin_views.admin_crypto_wallet_add,     name='admin_crypto_wallet_add'),
    path('crypto-wallets/<int:pk>/edit/',                admin_views.admin_crypto_wallet_edit,    name='admin_crypto_wallet_edit'),
    path('crypto-wallets/<int:pk>/toggle/',              admin_views.admin_crypto_wallet_toggle,  name='admin_crypto_wallet_toggle'),
]

# Investment management
urlpatterns += [
    path('investments/create/',            admin_views.admin_investment_create,   name='admin_investment_create'),
    path('investments/<uuid:pk>/',         admin_views.admin_investment_detail,   name='admin_investment_detail'),
    path('investments/<uuid:pk>/activate/',admin_views.admin_investment_activate, name='admin_investment_activate'),
    path('investments/<uuid:pk>/cancel/',  admin_views.admin_investment_cancel,   name='admin_investment_cancel'),
    path('investments/<uuid:pk>/complete/',admin_views.admin_investment_complete, name='admin_investment_complete'),
    path('investments/<uuid:pk>/adjust/',  admin_views.admin_investment_adjust,   name='admin_investment_adjust'),
]

# Platform settings
urlpatterns += [
    path('settings/', admin_views.admin_platform_settings, name='admin_platform_settings'),
]

# Platform bank accounts (full CRUD)
urlpatterns += [
    path('platform-accounts/add/',           admin_views.admin_bank_account_create, name='admin_bank_account_create'),
    path('platform-accounts/<int:pk>/edit/', admin_views.admin_bank_account_edit,   name='admin_bank_account_edit'),
    path('platform-accounts/<int:pk>/toggle/',admin_views.admin_bank_account_toggle,name='admin_bank_account_toggle'),
    path('platform-accounts/<int:pk>/delete/',admin_views.admin_bank_account_delete,name='admin_bank_account_delete'),
]

# Investment plan CRUD
urlpatterns += [
    path('plans/create/',           admin_views.admin_plan_create, name='admin_plan_create'),
    path('plans/<uuid:pk>/edit/',   admin_views.admin_plan_edit,   name='admin_plan_edit'),
    path('plans/<uuid:pk>/toggle/', admin_views.admin_plan_toggle, name='admin_plan_toggle'),
    path('plans/<uuid:pk>/delete/', admin_views.admin_plan_delete, name='admin_plan_delete'),
]

# Push notifications
from apps.notifications import views as notif_views
urlpatterns += [
    path('notifications/',       notif_views.admin_notifications,    name='admin_notifications'),
    path('notifications/send/',  notif_views.admin_send_notification, name='admin_send_notification'),
]

# Live support chat (admin side)
from apps.support.urls import admin_urlpatterns as chat_urls
urlpatterns += chat_urls
