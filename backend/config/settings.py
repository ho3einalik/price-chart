import os
import urllib.parse
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 't')
raw_secret = os.environ.get('DJANGO_SECRET_KEY', '')

if not DEBUG:
    if not raw_secret or raw_secret == 'dev-shoppilot-insecure-key-1234567890' or len(raw_secret) < 32:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a strong secret key (at least 32 characters) in production (DEBUG=False)."
        )
    SECRET_KEY = raw_secret

    raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(',') if h.strip()]
    if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must be explicitly defined and cannot contain '*' when DEBUG=False."
        )
else:
    SECRET_KEY = raw_secret or 'dev-shoppilot-insecure-key-1234567890'
    raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '*')
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(',') if h.strip()] or ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'django_filters',

    # ShopPilot Core Domain Apps
    'apps.accounts',
    'apps.tenancy',
    'apps.audit',
    'apps.catalog',
    'apps.inventory',
    'apps.orders',
    'apps.payments',
    'apps.fulfillment',
    'apps.daily_actions',
    'apps.analytics',
    'apps.tasks',
    'apps.social',
    'apps.features',
    'apps.suppliers',
    'apps.returns',
    'apps.finance',
    'apps.crm',
    'apps.social_inbox',
    'apps.marketing',
    'apps.automation',
    'apps.intelligence',
    'apps.wholesale_pos',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.tenancy.middleware.TenantContextMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
ASGI_APPLICATION = 'config.asgi.application'

# Database Configuration: support DATABASE_URL or DB_* environment variables
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_HOST = os.environ.get('DB_HOST')

if DATABASE_URL:
    parsed_db = urllib.parse.urlparse(DATABASE_URL)
    is_postgres = parsed_db.scheme in ('postgres', 'postgresql', 'pgsql')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql' if is_postgres else 'django.db.backends.sqlite3',
            'NAME': parsed_db.path.lstrip('/') if is_postgres else (BASE_DIR / parsed_db.path.lstrip('/')),
            'USER': parsed_db.username or '',
            'PASSWORD': parsed_db.password or '',
            'HOST': parsed_db.hostname or '',
            'PORT': str(parsed_db.port or 5432) if is_postgres else '',
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        }
    }
elif DB_HOST and not os.environ.get('USE_SQLITE'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'shoppilot'),
            'USER': os.environ.get('DB_USER', 'shoppilot_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'shoppilot_password'),
            'HOST': DB_HOST,
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        }
    }
else:
    if not DEBUG and not os.environ.get('ALLOW_SQLITE_IN_PRODUCTION'):
        raise ImproperlyConfigured(
            "Production database must be configured with PostgreSQL via DATABASE_URL or DB_HOST. "
            "SQLite is prohibited in production unless explicitly permitted with ALLOW_SQLITE_IN_PRODUCTION=True."
        )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# SimpleJWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'ShopPilot API',
    'DESCRIPTION': 'Enterprise Modular Multi-Tenant SaaS Operations & Intelligence API for E-Commerce',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# CORS Configuration
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'True').lower() in ('true', '1', 't')
else:
    CORS_ALLOW_ALL_ORIGINS = False

cors_origins_raw = os.environ.get('CORS_ALLOWED_ORIGINS', 'https://shoppilot.ir,https://app.shoppilot.ir')
CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_origins_raw.split(',') if o.strip()]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-store-id',  # Multi-tenant active store selection header
]

# Security Headers & Cookie Policies
if not DEBUG:
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
    CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True').lower() in ('true', '1', 't')
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    if os.environ.get('SECURE_PROXY_SSL_HEADER', 'True').lower() in ('true', '1', 't'):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    if os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 't'):
        SECURE_SSL_REDIRECT = True

    hsts_seconds = os.environ.get('SECURE_HSTS_SECONDS')
    if hsts_seconds:
        SECURE_HSTS_SECONDS = int(hsts_seconds)
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

    csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS')
    if csrf_origins:
        CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins.split(',') if o.strip()]
    elif CORS_ALLOWED_ORIGINS:
        CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# Celery & Redis Configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
