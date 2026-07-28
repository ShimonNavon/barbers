import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Prod compose always sets a real key; the fallback exists so local dev and
# CI never need env plumbing. Never deploy without DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-only-key")

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")

CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")
]

# TLS terminates at Cloudflare; host nginx forwards X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "catalog",
    "accounts",
    "community",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ["POSTGRES_USER"],
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": "5432",
        }
    }
else:
    # Local dev / tests run without Docker (house rule) — SQLite file
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "dev.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "he"
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    # defining STORAGES replaces Django's defaults entirely, so "default"
    # (media uploads) must be declared alongside whitenoise's staticfiles
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# The manifest only exists after collectstatic (image build). Local dev and
# tests use plain storage so {% static %} works without it.
if DEBUG or "test" in sys.argv:
    STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Shared cache (Valkey) — DRF throttling counts against it; falls back to
# local memory when REDIS_URL is unset so the app runs without the container.
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "barbershops": "20/hour",
    },
}

# Owner/master logins: permanent codes, each valid ONLY for its one phone.
# Env format: MASTER_OTP_PAIRS="+9725xxxxxxxx:code,+9725yyyyyyyy:code"
# Values live in the server's .env — never in git. Empty = disabled.
MASTER_OTP_PAIRS = {}
for _pair in os.environ.get("MASTER_OTP_PAIRS", "").split(","):
    if ":" in _pair:
        _phone, _code = _pair.strip().split(":", 1)
        MASTER_OTP_PAIRS[_phone] = _code

LOGIN_URL = "/login"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
