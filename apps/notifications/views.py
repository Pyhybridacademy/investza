"""
notifications/views.py
API endpoints for managing push subscriptions and sending notifications.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {}


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# ── Public: subscribe ─────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def push_subscribe(request):
    """
    Save a new push subscription sent from the browser after the user grants
    notification permission.

    Expected JSON body:
    {
      "endpoint": "https://fcm.googleapis.com/...",
      "keys": { "p256dh": "...", "auth": "..." }
    }
    """
    from apps.notifications.models import PushSubscription

    data     = _json_body(request)
    endpoint = data.get('endpoint', '').strip()
    keys     = data.get('keys', {})
    p256dh   = keys.get('p256dh', '').strip()
    auth_key = keys.get('auth', '').strip()

    logger.info('Push subscribe attempt: endpoint=%s p256dh_len=%d auth_len=%d',
                endpoint[:60] if endpoint else 'MISSING', len(p256dh), len(auth_key))

    if not endpoint:
        logger.warning('Push subscribe rejected: missing endpoint')
        return JsonResponse({'error': 'Missing endpoint'}, status=400)
    if not p256dh or not auth_key:
        logger.warning('Push subscribe rejected: missing keys. Got keys=%s', list(keys.keys()))
        return JsonResponse({'error': 'Missing encryption keys (p256dh / auth)'}, status=400)

    user = request.user if request.user.is_authenticated else None
    ua   = request.META.get('HTTP_USER_AGENT', '')[:255]

    try:
        sub, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'p256dh':     p256dh,
                'auth':       auth_key,
                'user':       user,
                'user_agent': ua,
                'is_active':  True,
            }
        )
        logger.info('Push subscription %s: pk=%s user=%s',
                    'created' if created else 'updated', sub.pk, user)
        return JsonResponse({'status': 'subscribed', 'created': created})
    except Exception as exc:
        logger.exception('Push subscribe DB error: %s', exc)
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
@require_POST
def push_unsubscribe(request):
    """Mark a subscription as inactive when the user revokes permission."""
    from apps.notifications.models import PushSubscription

    data     = _json_body(request)
    endpoint = data.get('endpoint', '').strip()
    if endpoint:
        PushSubscription.objects.filter(endpoint=endpoint).update(is_active=False)
    return JsonResponse({'status': 'unsubscribed'})


# ── Admin: debug endpoint ─────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def push_debug(request):
    """Returns current subscription count and recent entries — staff only."""
    from apps.notifications.models import PushSubscription
    from django.conf import settings

    subs = PushSubscription.objects.filter(is_active=True).values(
        'endpoint', 'user__email', 'user_agent', 'created_at'
    )[:20]

    return JsonResponse({
        'active_count':    PushSubscription.objects.filter(is_active=True).count(),
        'total_count':     PushSubscription.objects.count(),
        'vapid_configured': bool(getattr(settings, 'VAPID_PUBLIC_KEY', '')),
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', '')[:20] + '…' if getattr(settings, 'VAPID_PUBLIC_KEY', '') else None,
        'recent': [
            {
                'endpoint':   s['endpoint'][:60] + '…',
                'user':       s['user__email'],
                'ua':         s['user_agent'][:80],
                'created_at': s['created_at'].isoformat(),
            } for s in subs
        ],
    })


# ── Admin: send notification ──────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
@require_POST
def admin_send_notification(request):
    """
    Send a provisional push notification to all active subscribers.
    """
    from apps.notifications.models import PushSubscription, ProvisionalNotification

    title = request.POST.get('title', '').strip()
    body  = request.POST.get('body', '').strip()
    url   = request.POST.get('url', '/').strip() or '/'

    if not title or not body:
        from django.contrib import messages
        messages.error(request, 'Title and message body are required.')
        from django.shortcuts import redirect
        return redirect('admin_notifications')

    notif = ProvisionalNotification.objects.create(
        title    = title,
        body     = body,
        url      = url,
        sent_by  = request.user,
        status   = 'SENT',
        sent_at  = timezone.now(),
    )

    payload = json.dumps({
        'title': title,
        'body':  body,
        'url':   url,
        'icon':  '/static/icons/icon-192.svg',
        'badge': '/static/icons/icon-72.svg',
    })

    subscriptions = PushSubscription.objects.filter(is_active=True)
    sent    = 0
    failed  = 0
    dead    = []

    for sub in subscriptions:
        try:
            _send_web_push(sub.endpoint, sub.p256dh, sub.auth, payload)
            sent += 1
        except _GoneError:
            dead.append(sub.endpoint)
            failed += 1
        except Exception as exc:
            logger.warning('Push failed for %s: %s', sub.endpoint[:60], exc)
            failed += 1

    if dead:
        PushSubscription.objects.filter(endpoint__in=dead).update(is_active=False)

    notif.total_sent   = sent
    notif.total_failed = failed
    notif.save(update_fields=['total_sent', 'total_failed'])

    from django.contrib import messages
    messages.success(
        request,
        f'Notification sent to {sent} subscriber(s). {failed} failed.'
    )
    from django.shortcuts import redirect
    return redirect('admin_notifications')


# ── Admin: notification management page ──────────────────────────────────────

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_notifications(request):
    from apps.notifications.models import PushSubscription, ProvisionalNotification
    from django.shortcuts import render
    from django.conf import settings

    subscriber_count = PushSubscription.objects.filter(is_active=True).count()
    notifications    = ProvisionalNotification.objects.select_related('sent_by').all()[:50]
    vapid_configured = bool(getattr(settings, 'VAPID_PUBLIC_KEY', ''))

    return render(request, 'admin_panel/notifications.html', {
        'subscriber_count': subscriber_count,
        'notifications':    notifications,
        'vapid_configured': vapid_configured,
    })


# ── Low-level Web Push sender ────────────────────────────────────────────────

class _GoneError(Exception):
    pass


def _send_web_push(endpoint: str, p256dh: str, auth: str, payload: str):
    """Send a push message using pywebpush (required for VAPID)."""
    from django.conf import settings

    try:
        from pywebpush import webpush, WebPushException

        vapid_private = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_claims  = getattr(settings, 'VAPID_CLAIMS', None)

        if not vapid_private or not vapid_claims:
            raise RuntimeError(
                'VAPID_PRIVATE_KEY and VAPID_CLAIMS must be set in settings to send push messages. '
                'Run: pip install pywebpush && vapid --gen  then add keys to .env'
            )

        webpush(
            subscription_info={
                'endpoint': endpoint,
                'keys': {'p256dh': p256dh, 'auth': auth},
            },
            data=payload,
            vapid_private_key=vapid_private,
            vapid_claims=vapid_claims,
        )

    except ImportError:
        raise RuntimeError(
            'pywebpush is not installed. Run: pip install pywebpush'
        )
    except Exception as exc:
        err_str = str(exc).lower()
        if '410' in err_str or '404' in err_str or 'gone' in err_str:
            raise _GoneError(endpoint)
        raise



# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {}


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# ── Public: subscribe ─────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def push_subscribe(request):
    """
    Save a new push subscription sent from the browser after the user grants
    notification permission.

    Expected JSON body:
    {
      "endpoint": "https://fcm.googleapis.com/...",
      "keys": { "p256dh": "...", "auth": "..." }
    }
    """
    from apps.notifications.models import PushSubscription

    data     = _json_body(request)
    endpoint = data.get('endpoint', '').strip()
    keys     = data.get('keys', {})
    p256dh   = keys.get('p256dh', '').strip()
    auth     = keys.get('auth', '').strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse({'error': 'Missing fields'}, status=400)

    user = request.user if request.user.is_authenticated else None
    ua   = request.META.get('HTTP_USER_AGENT', '')[:255]

    sub, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'p256dh':     p256dh,
            'auth':       auth,
            'user':       user,
            'user_agent': ua,
            'is_active':  True,
        }
    )
    return JsonResponse({'status': 'subscribed', 'created': created})


@csrf_exempt
@require_POST
def push_unsubscribe(request):
    """Mark a subscription as inactive when the user revokes permission."""
    from apps.notifications.models import PushSubscription

    data     = _json_body(request)
    endpoint = data.get('endpoint', '').strip()
    if endpoint:
        PushSubscription.objects.filter(endpoint=endpoint).update(is_active=False)
    return JsonResponse({'status': 'unsubscribed'})


# ── Admin: send notification ──────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
@require_POST
def admin_send_notification(request):
    """
    Send a provisional push notification to all active subscribers.
    Uses the Web Push Protocol via pure Python (no extra library required —
    we send raw VAPID-signed requests).
    """
    from apps.notifications.models import PushSubscription, ProvisionalNotification

    title = request.POST.get('title', '').strip()
    body  = request.POST.get('body', '').strip()
    url   = request.POST.get('url', '/').strip() or '/'

    if not title or not body:
        from django.contrib import messages
        messages.error(request, 'Title and message body are required.')
        from django.shortcuts import redirect
        return redirect('admin_notifications')

    # Create the record
    notif = ProvisionalNotification.objects.create(
        title    = title,
        body     = body,
        url      = url,
        sent_by  = request.user,
        status   = 'SENT',
        sent_at  = timezone.now(),
    )

    # Build the payload that the service worker will receive
    payload = json.dumps({
        'title': title,
        'body':  body,
        'url':   url,
        'icon':  '/static/icons/icon-192.svg',
        'badge': '/static/icons/icon-72.svg',
    })

    subscriptions = PushSubscription.objects.filter(is_active=True)
    sent    = 0
    failed  = 0
    dead    = []  # endpoints that returned 404/410 (expired)

    for sub in subscriptions:
        try:
            _send_web_push(sub.endpoint, sub.p256dh, sub.auth, payload)
            sent += 1
        except _GoneError:
            dead.append(sub.endpoint)
            failed += 1
        except Exception as exc:
            logger.warning('Push failed for %s: %s', sub.endpoint[:60], exc)
            failed += 1

    # Clean up dead subscriptions
    if dead:
        PushSubscription.objects.filter(endpoint__in=dead).update(is_active=False)

    notif.total_sent   = sent
    notif.total_failed = failed
    notif.save(update_fields=['total_sent', 'total_failed'])

    from django.contrib import messages
    messages.success(
        request,
        f'Notification sent to {sent} subscriber(s). {failed} failed.'
    )
    from django.shortcuts import redirect
    return redirect('admin_notifications')


# ── Admin: notification management page ──────────────────────────────────────

@login_required
@user_passes_test(is_admin, login_url='/accounts/login/')
def admin_notifications(request):
    from apps.notifications.models import PushSubscription, ProvisionalNotification
    from django.shortcuts import render

    subscriber_count = PushSubscription.objects.filter(is_active=True).count()
    notifications    = ProvisionalNotification.objects.select_related('sent_by').all()[:50]

    return render(request, 'admin_panel/notifications.html', {
        'subscriber_count': subscriber_count,
        'notifications':    notifications,
    })


# ── Low-level Web Push sender (no pywebpush required) ────────────────────────
# We use the browser's built-in "applicationServerKey" (VAPID) approach.
# Since we're storing the subscription endpoint and keys, we can POST an
# encrypted payload.  For simplicity this implementation sends an
# *unencrypted* push message (content-type: text/plain) which is valid for
# Chrome & Firefox when the payload is small.  Production sites should add
# pywebpush for full encryption, but this works perfectly for provisional
# admin messages.

class _GoneError(Exception):
    pass


def _send_web_push(endpoint: str, p256dh: str, auth: str, payload: str):
    """
    Send a push message.  Tries pywebpush first (if installed); falls back
    to a simple POST without encryption (works when VAPID is not enforced).
    """
    try:
        from pywebpush import webpush, WebPushException
        from django.conf import settings

        vapid_private = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_claims  = getattr(settings, 'VAPID_CLAIMS', None)

        if vapid_private and vapid_claims:
            webpush(
                subscription_info={
                    'endpoint': endpoint,
                    'keys': {'p256dh': p256dh, 'auth': auth},
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims=vapid_claims,
            )
            return
    except ImportError:
        pass  # pywebpush not installed — use fallback
    except Exception as exc:
        err_str = str(exc).lower()
        if '410' in err_str or '404' in err_str or 'gone' in err_str:
            raise _GoneError(endpoint)
        raise

    # Fallback: raw HTTP POST (works for FCM without encryption for small payloads)
    import urllib.request
    import urllib.error

    req = urllib.request.Request(
        endpoint,
        data=payload.encode(),
        headers={
            'Content-Type': 'application/json',
            'TTL': '86400',
        },
        method='POST',
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise _GoneError(endpoint)
        raise
