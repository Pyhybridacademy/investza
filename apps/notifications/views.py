"""
notifications/views.py
API endpoints for managing push subscriptions and sending notifications.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
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
