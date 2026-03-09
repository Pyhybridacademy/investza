"""
accounts/emails.py
Centralised email sending utilities for the InvestZA platform.
All emails are sent as both HTML and plain-text alternatives.
"""
import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _base_context():
    """Shared context injected into every email."""
    return {
        'platform_name': getattr(settings, 'PLATFORM_NAME', 'InvestZA'),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@investza.co.za'),
        'support_phone': getattr(settings, 'SUPPORT_PHONE', '+27 (0) 10 000 0000'),
        'year': datetime.now().year,
    }


def _send(subject, to_email, html_template, context, txt_template=None):
    """
    Core send helper.
    Renders HTML template, strips it for plain-text fallback (or uses
    dedicated txt_template if provided), then sends via configured backend.
    """
    ctx = {**_base_context(), **context}

    html_content = render_to_string(html_template, ctx)

    if txt_template:
        text_content = render_to_string(txt_template, ctx)
    else:
        text_content = strip_tags(html_content)

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL',
                         f"{ctx['platform_name']} <noreply@investza.co.za>")

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[to_email],
    )
    msg.attach_alternative(html_content, 'text/html')

    try:
        msg.send(fail_silently=False)
        logger.info(f"Email sent: '{subject}' → {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email FAILED: '{subject}' → {to_email} | Error: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

def send_welcome_email(user, request=None):
    """Send welcome email after successful registration."""
    from django.urls import reverse
    if request:
        dashboard_url = request.build_absolute_uri(reverse('dashboard'))
    else:
        dashboard_url = f"https://investza.co.za/dashboard/"

    return _send(
        subject=f"Welcome to {getattr(settings, 'PLATFORM_NAME', 'InvestZA')} — Let's start investing!",
        to_email=user.email,
        html_template='emails/welcome.html',
        context={
            'user': user,
            'dashboard_url': dashboard_url,
        },
    )


def send_password_reset_email(user, reset_url):
    """Send password reset link email."""
    platform_name = getattr(settings, 'PLATFORM_NAME', 'InvestZA')
    return _send(
        subject=f"{platform_name} — Reset Your Password",
        to_email=user.email,
        html_template='emails/password_reset.html',
        txt_template='emails/password_reset.txt',
        context={
            'user': user,
            'reset_url': reset_url,
        },
    )


def send_password_changed_email(user, request=None):
    """Send confirmation email after a successful password change."""
    from django.urls import reverse
    platform_name = getattr(settings, 'PLATFORM_NAME', 'InvestZA')
    if request:
        login_url = request.build_absolute_uri(reverse('login'))
    else:
        login_url = f"https://investza.co.za/accounts/login/"

    return _send(
        subject=f"{platform_name} — Your password was changed",
        to_email=user.email,
        html_template='emails/password_changed.html',
        context={
            'user': user,
            'login_url': login_url,
        },
    )


def send_deposit_approved_email(user, deposit):
    """Notify user that their deposit has been approved."""
    platform_name = getattr(settings, 'PLATFORM_NAME', 'InvestZA')
    return _send(
        subject=f"{platform_name} — Deposit of R{deposit.amount:,.2f} Approved ✓",
        to_email=user.email,
        html_template='emails/deposit_approved.html',
        context={
            'user': user,
            'deposit': deposit,
        },
    )


def send_withdrawal_update_email(user, withdrawal):
    """Notify user of a withdrawal status change."""
    platform_name = getattr(settings, 'PLATFORM_NAME', 'InvestZA')
    status_label = withdrawal.get_status_display()
    return _send(
        subject=f"{platform_name} — Withdrawal {status_label}: R{withdrawal.amount:,.2f}",
        to_email=user.email,
        html_template='emails/withdrawal_update.html',
        context={
            'user': user,
            'withdrawal': withdrawal,
        },
    )
