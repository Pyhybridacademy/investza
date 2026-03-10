from django.urls import path
from apps.accounts import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('plans/', views.investment_plans_public, name='public_plans'),

    # Legal pages
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('risk-disclosure/', views.risk_disclosure, name='risk_disclosure'),
]

from apps.accounts.views import withdrawal_proofs
urlpatterns += [
    path('withdrawal-proofs/', withdrawal_proofs, name='withdrawal_proofs'),
]
