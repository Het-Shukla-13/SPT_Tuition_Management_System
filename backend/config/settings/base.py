"""
Base settings shared by every environment.

Environment-specific modules (development / production / test) import
everything from here and override only what differs. All secrets and
machine-specific values come from environment variables (read from
`backend/.env` locally) — nothing sensitive is ever hard-coded here.
"""

from datetime import timedelta
from pathlib import Path

import environ

# backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)

# ─────────────────────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.audit",
    "apps.academics",
    "apps.students",
    "apps.enquiries",
    "apps.learning",
    "apps.fees",
    "apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.common.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # (production.py inserts WhiteNoise here)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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

# ─────────────────────────────────────────────────────────────
# Database (PostgreSQL)
# DATABASE_URL format: postgres://USER:PASSWORD@HOST:PORT/DBNAME
# ─────────────────────────────────────────────────────────────
DATABASES = {"default": env.db("DATABASE_URL")}
# Reuse connections between requests instead of reconnecting every time,
# and verify a reused connection is still alive before handing it out.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─────────────────────────────────────────────────────────────
# Cache — shared store for throttling / rate limits.
# Default is a PostgreSQL-backed cache table (works across multiple
# server processes without Redis). Point CACHE_URL at Redis later
# (redis://...) without any code change.
# ─────────────────────────────────────────────────────────────
CACHES = {"default": env.cache("CACHE_URL", default="dbcache://django_cache")}

# ─────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─────────────────────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True  # store UTC in DB, convert at the edges

# ─────────────────────────────────────────────────────────────
# Static & media files
# ─────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Requests above these sizes are rejected before reaching our code.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB non-file request body
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # larger uploads stream to temp files
MAX_UPLOAD_SIZE_MB = env.int("MAX_UPLOAD_SIZE_MB", default=20)

# ─────────────────────────────────────────────────────────────
# Django REST Framework
# Secure by default: every endpoint requires a valid JWT unless the
# view explicitly opts out (e.g. health check, OTP request).
# ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.SessionJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.common.throttling.ResilientAnonRateThrottle",
        "apps.common.throttling.ResilientUserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_RATE_ANON", default="60/min"),
        "user": env("THROTTLE_RATE_USER", default="300/min"),
        # Per-IP limits on the public OTP endpoints (fail closed).
        "otp_request": env("THROTTLE_RATE_OTP_REQUEST", default="20/hour"),
        "otp_verify": env("THROTTLE_RATE_OTP_VERIFY", default="60/hour"),
        # Per-user limit on starting an email/phone change (also limits
        # probing which addresses are already registered).
        "enquiry": env("THROTTLE_RATE_ENQUIRY", default="5/hour"),
        "contact_change": env("THROTTLE_RATE_CONTACT_CHANGE", default="10/hour"),
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# ─────────────────────────────────────────────────────────────
# JWT (SimpleJWT)
# Short-lived access tokens; refresh tokens rotate on every use and the
# old one is blacklisted, so a stolen refresh token stops working as
# soon as the legitimate client refreshes.
# ─────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    # Tokens are stamped with and checked against these, so a token minted
    # by any other system that happens to share the key is rejected.
    "ISSUER": "spt-tms-api",
    "AUDIENCE": "spt-tms",
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Sessions (see apps/accounts/services/sessions.py)
# A refresh token rotated within this window may be presented again and gets
# the same new pair back (two tabs refreshing at once). After it: reuse
# detection revokes the session.
REFRESH_ROTATION_GRACE_SECONDS = env.int("REFRESH_ROTATION_GRACE_SECONDS", default=30)
# Hard cap: a login must be repeated after this, however actively it is refreshed.
SESSION_MAX_LIFETIME_DAYS = env.int("SESSION_MAX_LIFETIME_DAYS", default=30)

# ─────────────────────────────────────────────────────────────
# OTP authentication
# ─────────────────────────────────────────────────────────────
INSTITUTE_NAME = env("INSTITUTE_NAME", default="SPT Tuition Classes")

OTP_LENGTH = 6
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)  # 5 minutes
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)  # per OTP
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)
OTP_MAX_REQUESTS_PER_HOUR = env.int("OTP_MAX_REQUESTS_PER_HOUR", default=5)

# A bare 10-digit number like 9876543210 is assumed to be Indian.
DEFAULT_PHONE_COUNTRY_CODE = env("DEFAULT_PHONE_COUNTRY_CODE", default="+91")

# Console backend prints SMS to the terminal (development only). A real SMS
# gateway backend replaces it before production.
SMS_BACKEND = env("SMS_BACKEND", default="apps.accounts.services.sms.ConsoleSMSBackend")

# Student admission numbers look like SPT-2026-0001.
ADMISSION_NUMBER_PREFIX = env("ADMISSION_NUMBER_PREFIX", default="SPT")

# ─────────────────────────────────────────────────────────────
# Google Sign-In
# The OAuth *Client ID* (not a secret). A Google ID token is accepted only if
# it was issued for one of these client IDs (its `aud` claim), so tokens
# minted for any other app are rejected.
# ─────────────────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_ALLOWED_AUDIENCES = [
    aud
    for aud in [GOOGLE_OAUTH_CLIENT_ID, *env.list("GOOGLE_EXTRA_AUDIENCES", default=[])]
    if aud
]

# ─────────────────────────────────────────────────────────────
# API documentation (Swagger / OpenAPI)
# ─────────────────────────────────────────────────────────────
ENABLE_API_DOCS = env.bool("ENABLE_API_DOCS", default=True)

SPECTACULAR_SETTINGS = {
    "TITLE": "Tuition Management System API",
    "DESCRIPTION": "Backend API for the SPT Tuition Management System.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
    # Several components have a field called "status"; give each enum a clear name.
    "ENUM_NAME_OVERRIDES": {
        "StudentStatusEnum": "apps.students.models.StudentProfile.Status",
        "GoogleSignInStatusEnum": ["AUTHENTICATED", "OTP_REQUIRED"],
        "EnquiryStatusEnum": "apps.enquiries.models.AdmissionEnquiry.Status",
    },
}

# ─────────────────────────────────────────────────────────────
# CORS / CSRF — the frontend origin(s) allowed to call the API
# ─────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True  # needed later for an HttpOnly refresh-token cookie
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ─────────────────────────────────────────────────────────────
# Security headers that are safe in every environment
# ─────────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True

# ─────────────────────────────────────────────────────────────
# Email (OTP delivery). Console backend prints emails in development.
# ─────────────────────────────────────────────────────────────
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@localhost")

# ─────────────────────────────────────────────────────────────
# Logging — every line carries the request ID so one request can be
# traced across log lines. Never log OTPs, passwords or tokens.
# ─────────────────────────────────────────────────────────────
LOG_LEVEL = env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.common.log_filters.RequestIDLogFilter"},
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"level": "WARNING"},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
