"""
InvestZA - Root URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Django Admin (hidden path for security)
    path('platform-admin/', admin.site.urls),

    # Public pages
    path('', include('apps.accounts.urls.public')),

    # Authentication
    path('accounts/', include('apps.accounts.urls.auth')),

    # User Dashboard
    path('dashboard/', include('apps.accounts.urls.dashboard')),

    # Investments
    path('investments/', include('apps.investments.urls')),

    # Deposits
    path('deposits/', include('apps.deposits.urls')),

    # Withdrawals
    path('withdrawals/', include('apps.withdrawals.urls')),

    # Admin Panel (custom)
    path('admin-panel/', include('apps.administration.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
