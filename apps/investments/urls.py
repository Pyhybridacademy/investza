from django.urls import path
from . import views

urlpatterns = [
    path('', views.investment_list, name='investment_list'),
    path('create/', views.create_investment, name='create_investment'),
    path('create/<uuid:plan_id>/', views.create_investment, name='create_investment_plan'),
    path('my/', views.my_investments, name='my_investments'),
    path('<uuid:pk>/', views.investment_detail, name='investment_detail'),
    path('api/plan/<uuid:plan_id>/', views.get_plan_details, name='plan_api'),
]
