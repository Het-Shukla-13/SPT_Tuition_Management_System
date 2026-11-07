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
