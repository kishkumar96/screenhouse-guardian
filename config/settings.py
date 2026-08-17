"""
Screen House Guardian — Django settings.

Environment variable handling: django-environ
Database: PostgreSQL via DATABASE_URL env var; falls back to SQLite for quick
local development so that `python manage.py check` works without a running
Postgres instance.

Assumption: SQLite is acceptable only for local scaffolding and CI smoke
tests. All real deployments must point DATABASE_URL at PostgreSQL.
"""

import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    CSRF_TRUSTED_ORIGINS=(list, []),
)

environ.Env.read_env(BASE_DIR / '.env')

# ── Core ──────────────────────────────────────────────────────────────────────

# The django-insecure- prefix explicitly marks this as a dev-only default.
# Never keep this value in production; always override via SECRET_KEY env var.
SECRET_KEY = env(
    'SECRET_KEY',
    default='django-insecure-dev-placeholder-override-in-production',
)

# Default to DEBUG=True for local development when no .env is present.
# Production must explicitly set DEBUG=False via environment.
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS')

# ── Applications ──────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'inventory.apps.InventoryConfig',
    'monitoring.apps.MonitoringConfig',
    'qr.apps.QrConfig',
    'dashboard.apps.DashboardConfig',
    'exports.apps.ExportsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
# Set DATABASE_URL in .env for PostgreSQL.
# Default SQLite path is for local development only; never for production.

DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
    )
}

# ── Auth ──────────────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ── Internationalisation ──────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Static and media ──────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# CompressedManifestStaticFilesStorage requires collectstatic to have run
# (it reads a JSON manifest for cache-busted filenames) — only safe once
# DEBUG=False, i.e. in an image that ran collectstatic at build time.
# Local dev/test use the plain storage so `{% static %}` works unmodified.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
            if not DEBUG else
            'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Production hardening ────────────────────────────────────────────────────
# Only applied when DEBUG=False, so local development is unaffected.
# Assumes the app sits behind a TLS-terminating proxy/load balancer that
# sets X-Forwarded-Proto (true for most PaaS providers and typical nginx
# reverse-proxy setups) — adjust SECURE_PROXY_SSL_HEADER if that's not the case.

if not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7  # 1 week; raise once HTTPS is confirmed stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ── Misc ──────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
