"""
Settings for the automated test suite (pytest).

Uses the same PostgreSQL server as development (pytest-django creates and
destroys a separate `test_<dbname>` database), so tests exercise real
PostgreSQL behaviour such as constraints and locking.
"""

from .base import *  # noqa: F403

DEBUG = False

# Fast hashing — tests create many users.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Isolated in-memory cache and mailbox per test run.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SMS_BACKEND = "apps.accounts.services.sms.LocmemSMSBackend"

# Tests never call Google; token verification is mocked.
GOOGLE_OAUTH_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
GOOGLE_ALLOWED_AUDIENCES = [GOOGLE_OAUTH_CLIENT_ID]

# Tests never talk to Google Drive: files go to local (temporary) storage.
STORAGES = {
    **STORAGES,  # noqa: F405
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

# Most tests read the refresh token from the body; cookie tests switch this off.
REFRESH_TOKEN_IN_BODY = True
