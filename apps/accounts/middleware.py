from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class LastSeenMiddleware:
    """Update user's last_seen timestamp on every request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            request.user.__class__.objects.filter(pk=request.user.pk).update(
                last_seen=timezone.now()
            )
        return response


# ── Simple in-process cache so we don't hit the DB on every request ──────────
import time
_maint_cache = {'value': None, 'message': '', 'ts': 0}
_CACHE_TTL   = 30  # seconds — low enough to feel instant, high enough to not hammer DB


def _get_maintenance_state():
    """Return (maintenance_mode: bool, message: str) with a 30s in-process cache."""
    now = time.monotonic()
    if now - _maint_cache['ts'] < _CACHE_TTL and _maint_cache['value'] is not None:
        return _maint_cache['value'], _maint_cache['message']
    try:
        from apps.accounts.models import PlatformSettings
        ps = PlatformSettings.objects.only('maintenance_mode', 'maintenance_message').get(pk=1)
        _maint_cache.update({'value': ps.maintenance_mode, 'message': ps.maintenance_message, 'ts': now})
        return ps.maintenance_mode, ps.maintenance_message
    except Exception:
        # Table may not exist yet (pre-migration) — treat as off
        _maint_cache.update({'value': False, 'message': '', 'ts': now})
        return False, ''


def invalidate_maintenance_cache():
    """Call this after saving PlatformSettings so the change takes effect immediately."""
    _maint_cache['ts'] = 0


# Paths that are ALWAYS allowed even in maintenance mode
_ALWAYS_ALLOWED_PREFIXES = (
    '/platform-admin/',   # Django admin — superuser access
    '/admin-panel/',      # Custom admin panel — staff access
    '/static/',           # Static files
    '/media/',            # Media files
    '/robots.txt',
    '/sitemap.xml',
    '/sw.js',
    '/favicon',
)


class MaintenanceModeMiddleware:
    """
    Intercepts all requests when PlatformSettings.maintenance_mode is True.

    Rules:
      - Superusers and staff always pass through (they can still manage the platform).
      - The custom admin panel and Django admin are always accessible.
      - Static/media files and SEO files are always accessible.
      - Everyone else sees the 503 maintenance page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Always allow certain paths without even checking the DB
        for prefix in _ALWAYS_ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return self.get_response(request)

        # Staff / superusers always pass through
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return self.get_response(request)

        # Check maintenance state (cached)
        active, message = _get_maintenance_state()
        if active:
            return self._maintenance_response(request, message)

        return self.get_response(request)

    def _maintenance_response(self, request, message):
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        try:
            ps = self._get_platform_settings()
            html = render_to_string('503.html', {
                'maintenance_message': message,
                'PLATFORM_NAME':    ps.get('platform_name', 'InvestZA'),
                'SUPPORT_EMAIL':    ps.get('support_email', ''),
                'SUPPORT_PHONE':    ps.get('support_phone', ''),
                'SUPPORT_WHATSAPP': ps.get('support_whatsapp', ''),
            }, request=request)
        except Exception:
            html = f"""<!DOCTYPE html><html><head><title>Maintenance</title></head>
<body style="font-family:sans-serif;text-align:center;padding:80px 24px;background:#03071e;color:#fff;">
<h1 style="color:#fac660;font-size:2rem;margin-bottom:16px;">Under Maintenance</h1>
<p style="color:rgba(255,255,255,0.6);">{message or 'We will be back shortly.'}</p>
</body></html>"""
        return HttpResponse(html, status=503, content_type='text/html')

    @staticmethod
    def _get_platform_name():
        try:
            from apps.accounts.models import PlatformSettings
            return PlatformSettings.objects.values_list('platform_name', flat=True).get(pk=1)
        except Exception:
            return 'InvestZA'
