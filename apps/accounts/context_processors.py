from django.conf import settings


def platform_settings(request):
    """Inject platform-wide settings into every template context."""
    return {
        'PLATFORM_NAME': getattr(settings, 'PLATFORM_NAME', 'InvestZA'),
        'PLATFORM_CURRENCY': getattr(settings, 'PLATFORM_CURRENCY', 'ZAR'),
        'PLATFORM_CURRENCY_SYMBOL': getattr(settings, 'PLATFORM_CURRENCY_SYMBOL', 'R'),
        'SUPPORT_EMAIL': getattr(settings, 'SUPPORT_EMAIL', 'support@investza.co.za'),
        'SUPPORT_PHONE': getattr(settings, 'SUPPORT_PHONE', '+27 (0) 10 000 0000'),
    }
