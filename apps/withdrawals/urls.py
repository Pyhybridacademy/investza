from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.withdrawal_home,         name='withdrawal_home'),
    path('create/',                             views.create_withdrawal,       name='create_withdrawal'),
    path('create/step2/',                       views.withdrawal_step2,        name='withdrawal_step2'),
    path('create/step3/',                       views.withdrawal_step3,        name='withdrawal_step3'),
    path('complete/<uuid:pk>/',                 views.withdrawal_complete,     name='withdrawal_complete'),
    path('history/',                            views.withdrawal_history,      name='withdrawal_history'),
    path('detail/<uuid:pk>/',                   views.withdrawal_detail,       name='withdrawal_detail'),
    path('tax-cert/<uuid:pk>/download/',        views.download_tax_certificate,name='download_tax_cert'),
]
