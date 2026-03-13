"""
InvestZA Platform - Django Settings
Multi-Asset Investment Platform for South Africa
"""

import os
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── SECURITY ────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-0-pq1ki2dc@1=mxe*%!5(uj(fxpvi7ibyu2s-^(fvrr*cf(_ls')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,investza.onrender.com', cast=Csv())

# ─── APPLICATIONS ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django_daisy',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Third-party
    'rest_framework',
    'crispy_forms',
    'crispy_tailwind',
    'widget_tweaks',
    'corsheaders',

    # Platform apps
    'apps.accounts',
    'apps.investments',
    'apps.deposits',
    'apps.withdrawals',
    'apps.administration',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.accounts.middleware.LastSeenMiddleware',
    # Maintenance mode — runs after auth so we know if user is staff
    'apps.accounts.middleware.MaintenanceModeMiddleware',
]

ROOT_URLCONF = 'investza.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.accounts.context_processors.platform_settings',
                'apps.accounts.context_processors.admin_pending_counts',
            ],
        },
    },
]

WSGI_APPLICATION = 'investza.wsgi.application'

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# To use PostgreSQL, replace above with:
# import dj_database_url
# DATABASES = {'default': dj_database_url.parse(config('DATABASE_URL'))}

# ─── AUTHENTICATION ───────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── INTERNATIONALIZATION ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-za'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

# ─── STATIC & MEDIA FILES ─────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── EMAIL ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='InvestZA <noreply@investza.co.za>')

# Token expires in 24 hours (86400 seconds)
PASSWORD_RESET_TIMEOUT = 86400

# ─── CELERY (Task Queue) ──────────────────────────────────────────────────────
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_TIMEZONE = TIME_ZONE

# ─── CRISPY FORMS ─────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'tailwind'
CRISPY_TEMPLATE_PACK = 'tailwind'

# ─── REST FRAMEWORK ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ─── PLATFORM SETTINGS ────────────────────────────────────────────────────────
PLATFORM_NAME = config('PLATFORM_NAME', default='InvestZA')
PLATFORM_CURRENCY = config('PLATFORM_CURRENCY', default='ZAR')
PLATFORM_CURRENCY_SYMBOL = config('PLATFORM_CURRENCY_SYMBOL', default='R')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='support@investza.co.za')
SUPPORT_PHONE = config('SUPPORT_PHONE', default='+27 (0) 10 000 0000')

MIN_DEPOSIT = config('MIN_DEPOSIT', default=500, cast=float)
MAX_DEPOSIT = config('MAX_DEPOSIT', default=5000000, cast=float)
MIN_WITHDRAWAL = config('MIN_WITHDRAWAL', default=200, cast=float)
MAX_WITHDRAWAL = config('MAX_WITHDRAWAL', default=1000000, cast=float)

# ─── SECURITY HEADERS (enable in production) ──────────────────────────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=86400, cast=int)


CSRF_TRUSTED_ORIGINS = ['https://investza.onrender.com']

# ─── WEB PUSH / VAPID ─────────────────────────────────────────────────────────
# Optional: generate VAPID keys with: pip install pywebpush && vapid --gen
# Then set in .env:  VAPID_PRIVATE_KEY=...  VAPID_PUBLIC_KEY=...
# Without VAPID, push still works on most browsers via the fallback path.
VAPID_PRIVATE_KEY = config('VAPID_PRIVATE_KEY', default='')
VAPID_PUBLIC_KEY  = config('VAPID_PUBLIC_KEY',  default='')
VAPID_CLAIMS      = {
    'sub': 'mailto:' + config('SUPPORT_EMAIL', default='support@investza.co.za'),
} if config('VAPID_PRIVATE_KEY', default='') else None


# ─── LOGGING (shows push notification activity in Render logs) ────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'apps.notifications': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
