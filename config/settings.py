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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Misc ──────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
