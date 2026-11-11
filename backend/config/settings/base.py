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
    "apps.common.middleware.RequestLoggingMiddleware",
    "apps.common.middleware.SecurityHeadersMiddleware",
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
# Django admin site path. Change it in production (e.g. "control-7f3a/") so it
# isn't found by bots scanning for /admin/.
DJANGO_ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")
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
# Fail fast instead of hanging: give up connecting after DB_CONNECT_TIMEOUT
# seconds, and cancel any single query running longer than
# DB_STATEMENT_TIMEOUT_MS (0 = no limit; migrations run with 0).
_statement_timeout_ms = env.int("DB_STATEMENT_TIMEOUT_MS", default=30_000)
DATABASES["default"].setdefault("OPTIONS", {}).update(
    {
        "connect_timeout": env.int("DB_CONNECT_TIMEOUT", default=5),
        "options": f"-c statement_timeout={_statement_timeout_ms}",
    }
)

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

# Google Drive file storage (Phase 6). When all four are set, uploaded files
# (PDFs, photos) go to a private folder in the owner's Drive instead of the
# local disk. Set up with: python manage.py google_drive_connect
GOOGLE_DRIVE_CLIENT_ID = env("GOOGLE_DRIVE_CLIENT_ID", default="")
GOOGLE_DRIVE_CLIENT_SECRET = env("GOOGLE_DRIVE_CLIENT_SECRET", default="")
GOOGLE_DRIVE_REFRESH_TOKEN = env("GOOGLE_DRIVE_REFRESH_TOKEN", default="")
GOOGLE_DRIVE_FOLDER_ID = env("GOOGLE_DRIVE_FOLDER_ID", default="")
if all(
    (
        GOOGLE_DRIVE_CLIENT_ID,
        GOOGLE_DRIVE_CLIENT_SECRET,
        GOOGLE_DRIVE_REFRESH_TOKEN,
        GOOGLE_DRIVE_FOLDER_ID,
    )
):
    STORAGES["default"] = {"BACKEND": "apps.common.storage.GoogleDriveStorage"}

MAX_PHOTO_SIZE_MB = env.int("MAX_PHOTO_SIZE_MB", default=5)

# Requests above these sizes are rejected before reaching our code.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB non-file request body
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # larger uploads stream to temp files
MAX_UPLOAD_SIZE_MB = env.int("MAX_UPLOAD_SIZE_MB", default=20)

# ─────────────────────────────────────────────────────────────
# Django REST Framework
# Secure by default: every endpoint requires a valid JWT unless the
# view explicitly opts out (e.g. health check, OTP request).
# ─────────────────────────────────────────────────────────────
# Number of reverse proxies in front of Django that append to X-Forwarded-For
# (1 behind our Caddy). 0 = trust only REMOTE_ADDR (direct connections, local
# dev). Never set it higher than the real number of proxies: the extra entries
# are client-controlled and would let anyone fake their IP past rate limits.
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)

REST_FRAMEWORK = {
    "NUM_PROXIES": TRUSTED_PROXY_COUNT
    or None,  # DRF throttles: same rule as client_ip()
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
        # Per-IP limit on password logins (on top of the per-email lockout).
        "login": env("THROTTLE_RATE_LOGIN", default="60/hour"),
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
INSTITUTE_NAME = env("INSTITUTE_NAME", default="Sai Personal Tuitions")

OTP_LENGTH = 6
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)  # 5 minutes
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)  # per OTP
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)
OTP_MAX_REQUESTS_PER_HOUR = env.int("OTP_MAX_REQUESTS_PER_HOUR", default=5)

# Password login + trusted devices (Phase 1.5, docs/plans/phase-1-5-password-login.md).
# A device that passed the emailed-code check skips it for this many days.
TRUSTED_DEVICE_DAYS = env.int("TRUSTED_DEVICE_DAYS", default=90)
DEVICE_COOKIE_NAME = "tms_device"
# Wrong passwords per email before a lockout, and the lockout length.
LOGIN_MAX_FAILURES = env.int("LOGIN_MAX_FAILURES", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)
# How long the browser has to enter the new-device code after the password.
LOGIN_TICKET_MAX_AGE_SECONDS = env.int("LOGIN_TICKET_MAX_AGE_SECONDS", default=15 * 60)

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
    "DESCRIPTION": "Backend API for Chalkboard, the app of Sai Personal Tuitions.",
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
CORS_ALLOW_CREDENTIALS = True  # the frontend sends the HttpOnly refresh-token cookie
# Headers the frontend's JavaScript may read: the request id (for error reports)
# and Content-Disposition (file names of downloads).
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Content-Disposition"]

# Refresh token cookie (see apps/accounts/services/auth_cookies.py).
REFRESH_COOKIE_NAME = "tms_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"  # sent only to the auth endpoints
REFRESH_COOKIE_SECURE = env.bool("REFRESH_COOKIE_SECURE", default=True)
# "Lax" needs the frontend and API on the same site (see the Phase 9 plan).
REFRESH_COOKIE_SAMESITE = env("REFRESH_COOKIE_SAMESITE", default="Lax")
REFRESH_COOKIE_DOMAIN = env("REFRESH_COOKIE_DOMAIN", default=None)
# Also return the refresh token in JSON bodies (Swagger/dev convenience).
REFRESH_TOKEN_IN_BODY = env.bool("REFRESH_TOKEN_IN_BODY", default=False)
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
LOG_FORMAT = env("LOG_FORMAT", default="text")  # "json" on hosting platforms
SLOW_REQUEST_MS = env.int("SLOW_REQUEST_MS", default=1000)

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
        "json": {"()": "apps.common.log_formatters.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "standard",
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


# ─────────────────────────────────────────────────────────────
# Error monitoring (optional): set SENTRY_DSN (free tier) to receive crash
# reports. Personal data is never sent (no IPs, cookies, headers or bodies).
# ─────────────────────────────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="development"),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )

# ─────────────────────────────────────────────────────────────
# Backups & scheduled jobs (Phase 8)
# ─────────────────────────────────────────────────────────────
# Where `backup_database` writes dumps, how many it keeps (locally and in
# Google Drive), and where the PostgreSQL client tools live ("" = on PATH;
# on Windows e.g. "C:/Program Files/PostgreSQL/18/bin").
BACKUP_DIR = Path(env("BACKUP_DIR", default=str(BASE_DIR / "backups")))
BACKUP_KEEP = env.int("BACKUP_KEEP", default=14)
BACKUP_TO_DRIVE = env.bool("BACKUP_TO_DRIVE", default=True)
PG_BIN_DIR = env("PG_BIN_DIR", default="")

# How long finished OTP challenges and ended login sessions are kept (audit
# trail) before `purge_expired_records` deletes them.
OTP_RETENTION_DAYS = env.int("OTP_RETENTION_DAYS", default=90)
SESSION_RETENTION_DAYS = env.int("SESSION_RETENTION_DAYS", default=90)

# Daily jobs run by `python manage.py run_scheduler` (times in TIME_ZONE).
SCHEDULED_JOBS = [
    {"command": "backup_database", "at": env("BACKUP_TIME", default="02:30")},
    {"command": "purge_expired_records", "at": "03:15"},
]
