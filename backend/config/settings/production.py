"""
Production settings.

Everything here assumes the app runs behind HTTPS (the hosting provider's
proxy terminates TLS and sets X-Forwarded-Proto).
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, MIDDLEWARE, SECRET_KEY, STORAGES, env

DEBUG = False

# WhiteNoise serves static files (admin CSS, Swagger assets) directly from
# the app server; it must sit right after SecurityMiddleware.
MIDDLEWARE = [*MIDDLEWARE]
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is too weak for production.")

# HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# Preload is effectively irreversible (browsers hard-code the domain), so it
# stays off until the final domain has run on HTTPS for a while.
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
if not SECURE_HSTS_PRELOAD:
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Cookies only over HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Hashed + compressed static files served by WhiteNoise
STORAGES = {
    **STORAGES,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Swagger is off in production unless explicitly enabled.
ENABLE_API_DOCS = env.bool("ENABLE_API_DOCS", default=False)
