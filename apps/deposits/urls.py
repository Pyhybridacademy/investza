from django.urls import path
from . import views

urlpatterns = [
    path('',                        views.deposit_home,            name='deposit_home'),
    path('bank/',                   views.bank_deposit_create,     name='bank_deposit_create'),
    path('bank/<uuid:pk>/',         views.bank_deposit_detail,     name='bank_deposit_detail'),
    path('crypto/',                 views.crypto_deposit_create,   name='crypto_deposit_create'),
    path('crypto/<uuid:pk>/',       views.crypto_deposit_detail,   name='crypto_deposit_detail'),
    path('history/',                views.deposit_history,         name='deposit_history'),
    path('api/crypto-price/',       views.crypto_price_api,        name='crypto_price_api'),
]
