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


def admin_pending_counts(request):
    """Inject pending action counts for the admin sidebar badge indicators."""
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return {}
    try:
        from apps.deposits.models import BankDeposit, CryptoDeposit
        from apps.withdrawals.models import Withdrawal
        pending_deposits = (
            BankDeposit.objects.filter(status__in=['SUBMITTED', 'VERIFYING']).count() +
            CryptoDeposit.objects.filter(status__in=['SUBMITTED', 'VERIFYING']).count()
        )
        pending_withdrawals = Withdrawal.objects.filter(status='PENDING').count()
        return {
            'pending_deposits_count': pending_deposits,
            'pending_withdrawals_count': pending_withdrawals,
        }
    except Exception:
        return {}

