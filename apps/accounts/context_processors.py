from django.conf import settings


def platform_settings(request):
    """
    Inject platform-wide settings into every template context.
    Reads from PlatformSettings DB model first, falls back to .env / settings.py.
    """
    try:
        from apps.accounts.models import PlatformSettings
        ps = PlatformSettings.get()
        return {
            'PLATFORM_NAME':            ps.platform_name,
            'PLATFORM_CURRENCY':        ps.currency_code,
            'PLATFORM_CURRENCY_SYMBOL': ps.currency_symbol,
            'SUPPORT_EMAIL':            ps.support_email,
            'SUPPORT_PHONE':            ps.support_phone,
            'SUPPORT_WHATSAPP':         ps.support_whatsapp,
            'PLATFORM_TAGLINE':         ps.tagline,
            'PLATFORM_FSP':             ps.fsp_number,
            'PLATFORM_SETTINGS':        ps,   # full object available in templates
            'MIN_DEPOSIT':              ps.min_deposit,
            'MAX_DEPOSIT':              ps.max_deposit,
            'MIN_WITHDRAWAL':           ps.min_withdrawal,
            'MAX_WITHDRAWAL':           ps.max_withdrawal,
            'MAINTENANCE_MODE':         ps.maintenance_mode,
            'VAPID_PUBLIC_KEY':         getattr(settings, 'VAPID_PUBLIC_KEY', ''),
        }
    except Exception:
        # Fallback to .env / settings defaults if DB not yet migrated
        return {
            'PLATFORM_NAME':            getattr(settings, 'PLATFORM_NAME', 'InvestZA'),
            'PLATFORM_CURRENCY':        getattr(settings, 'PLATFORM_CURRENCY', 'ZAR'),
            'PLATFORM_CURRENCY_SYMBOL': getattr(settings, 'PLATFORM_CURRENCY_SYMBOL', 'R'),
            'SUPPORT_EMAIL':            getattr(settings, 'SUPPORT_EMAIL', 'support@investza.co.za'),
            'SUPPORT_PHONE':            getattr(settings, 'SUPPORT_PHONE', '+27 (0) 10 000 0000'),
            'SUPPORT_WHATSAPP':         '',
            'PLATFORM_TAGLINE':         'Invest with Confidence',
            'PLATFORM_FSP':             '',
            'PLATFORM_SETTINGS':        None,
            'MIN_DEPOSIT':              getattr(settings, 'MIN_DEPOSIT', 500),
            'MAX_DEPOSIT':              getattr(settings, 'MAX_DEPOSIT', 5000000),
            'MIN_WITHDRAWAL':           getattr(settings, 'MIN_WITHDRAWAL', 200),
            'MAX_WITHDRAWAL':           getattr(settings, 'MAX_WITHDRAWAL', 1000000),
            'MAINTENANCE_MODE':         False,
            'VAPID_PUBLIC_KEY':         getattr(settings, 'VAPID_PUBLIC_KEY', ''),
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
            'pending_deposits_count':    pending_deposits,
            'pending_withdrawals_count': pending_withdrawals,
        }
    except Exception:
        return {}
