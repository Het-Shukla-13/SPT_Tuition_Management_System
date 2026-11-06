"""
Per-identity OTP request limits: a resend cooldown and an hourly cap.

These apply to the email/phone being targeted, on top of the per-IP
throttle, so one attacker using many IPs still can't flood a victim's inbox.

Cache outage policy (pattern from Labe1's two-factor helpers): FAIL CLOSED.
If the counters can't be read, the request is refused with a 503 instead of
being allowed, otherwise a cache outage would switch off flood protection.

The limits apply identically whether or not an account exists, so their
behaviour reveals nothing about who is registered.
"""

import hashlib
import logging
import math
import time

from django.conf import settings
from django.core.cache import cache

from apps.accounts.exceptions import (
    OTPCooldown,
    OTPRequestLimitReached,
    OTPServiceUnavailable,
)

logger = logging.getLogger(__name__)

HOUR = 60 * 60


def _key(kind: str, channel: str, identifier: str, purpose: str) -> str:
    # Hash the identifier so emails/phone numbers never sit in the cache in plain text.
    digest = hashlib.sha256(f"{channel}:{identifier}".encode()).hexdigest()[:32]
    return f"otp:{kind}:{purpose}:{digest}"


def reserve_otp_request(*, channel: str, identifier: str, purpose: str) -> None:
    """
    Claim the right to send an OTP now, or raise.

    `cache.add` is atomic (it only writes if the key is absent), so two
    simultaneous requests can't both pass the cooldown.
    """
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
    cooldown_key = _key("cooldown", channel, identifier, purpose)
    hourly_key = _key("hourly", channel, identifier, purpose)
    now = time.time()

    try:
        if not cache.add(cooldown_key, now, timeout=cooldown):
            started = cache.get(cooldown_key) or now
            remaining = max(1, math.ceil(cooldown - (now - started)))
            raise OTPCooldown(wait=remaining)

        cache.add(hourly_key, 0, timeout=HOUR)
        count = cache.incr(hourly_key)
    except OTPCooldown:
        raise
    except Exception:
        logger.exception(
            "OTP rate-limit store unavailable - refusing request (fail closed)."
        )
        raise OTPServiceUnavailable() from None

    if count > settings.OTP_MAX_REQUESTS_PER_HOUR:
        raise OTPRequestLimitReached()
