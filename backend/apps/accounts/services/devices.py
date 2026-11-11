"""
Trusted devices (Phase 1.5): "this browser already passed the emailed code".

The browser holds a random 256-bit token in the HttpOnly `tms_device` cookie;
the database stores only its SHA-256. A plain hash is right here (unlike for
passwords): the token is long and random, so it can't be guessed or brute-forced
from the hash, and lookups stay a single indexed query.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import TrustedDevice, User

logger = logging.getLogger(__name__)


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def device_token_from(request) -> str | None:
    token = request.COOKIES.get(settings.DEVICE_COOKIE_NAME)
    # A real token is ~43 characters; anything else is junk, not a lookup.
    return token if token and 20 <= len(token) <= 128 else None


def find_trusted_device(user: User, token: str | None) -> TrustedDevice | None:
    if not token:
        return None
    return (
        TrustedDevice.objects.active()
        .filter(user=user, token_hash=hash_device_token(token))
        .first()
    )


def is_trusted(user: User, token: str | None) -> bool:
    """True if this browser is trusted for this user; marks it as just used."""
    device = find_trusted_device(user, token)
    if device is None:
        return False
    TrustedDevice.objects.filter(pk=device.pk).update(last_used_at=timezone.now())
    return True


def trust_device(
    user: User, *, token: str | None, ip=None, user_agent: str = ""
) -> str:
    """
    Trust this browser for this user for TRUSTED_DEVICE_DAYS, starting now.
    Reuses the browser's existing token (another family member may already
    trust it) or creates one. Returns the token to put in the cookie.
    """
    token = token or new_device_token()
    token_hash = hash_device_token(token)
    values = {
        "label": (user_agent or "")[:512],
        "ip_address": ip,
        "expires_at": timezone.now() + timedelta(days=settings.TRUSTED_DEVICE_DAYS),
        "last_used_at": timezone.now(),
        "revoked_at": None,
        "revoked_reason": "",
    }
    try:
        with transaction.atomic():
            TrustedDevice.objects.update_or_create(
                user=user, token_hash=token_hash, defaults=values
            )
    except IntegrityError:
        # Two simultaneous verifications from one browser: the other one won.
        TrustedDevice.objects.filter(user=user, token_hash=token_hash).update(**values)
    logger.info("Device trusted: user_id=%s", user.pk)
    return token


def revoke_trusted_devices(
    user: User, reason: str, *, keep_token: str | None = None
) -> int:
    """Untrust every device of `user` (except the one holding `keep_token`)."""
    queryset = TrustedDevice.objects.filter(user=user, revoked_at__isnull=True)
    if keep_token:
        queryset = queryset.exclude(token_hash=hash_device_token(keep_token))
    count = queryset.update(revoked_at=timezone.now(), revoked_reason=reason)
    if count:
        logger.info(
            "Untrusted %s device(s): user_id=%s reason=%s", count, user.pk, reason
        )
    return count
