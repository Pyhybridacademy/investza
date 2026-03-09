"""
InvestZA - Root URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import HttpResponse, FileResponse
from django.views.decorators.cache import cache_control
import os


# ── SEO / PWA views (no extra packages needed) ──────────────────────────────

@cache_control(max_age=86400)
def robots_txt(request):
    host = request.build_absolute_uri('/').rstrip('/')
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /dashboard/',
        'Disallow: /accounts/',
        'Disallow: /deposits/',
        'Disallow: /withdrawals/',
        'Disallow: /investments/',
        'Disallow: /admin-panel/',
        'Disallow: /platform-admin/',
        'Disallow: /api/',
        '',
        f'Sitemap: {host}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@cache_control(max_age=3600)
def sitemap_xml(request):
    host = request.build_absolute_uri('/').rstrip('/')
    from django.utils.timezone import now
    today = now().strftime('%Y-%m-%d')
    urls = [
        ('/', '1.0', 'weekly'),
        ('/about/', '0.7', 'monthly'),
        ('/plans/', '0.8', 'weekly'),
        ('/contact/', '0.5', 'monthly'),
        ('/terms/', '0.3', 'yearly'),
        ('/privacy/', '0.3', 'yearly'),
        ('/risk-disclosure/', '0.3', 'yearly'),
    ]
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, priority, freq in urls:
        xml_parts.append(
            f'  <url><loc>{host}{loc}</loc><lastmod>{today}</lastmod>'
            f'<changefreq>{freq}</changefreq><priority>{priority}</priority></url>'
        )
    xml_parts.append('</urlset>')
    return HttpResponse('\n'.join(xml_parts), content_type='application/xml')


@cache_control(max_age=86400)
def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'pwa', 'sw.js')
    if not os.path.exists(sw_path):
        sw_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'pwa', 'sw.js')
    response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response


urlpatterns = [
    # SEO & PWA
    path('robots.txt', robots_txt),
    path('sitemap.xml', sitemap_xml),
    path('sw.js', service_worker),

    # Django Admin
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
