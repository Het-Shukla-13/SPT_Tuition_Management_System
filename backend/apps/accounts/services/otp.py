"""
OTP issuing and verification: the core of sign-up and login.

request_otp()  -> rate-limit, decide whether to send, store a hashed code, deliver.
verify_otp()   -> check the code under a row lock, then create (REGISTER) or
                  fetch (LOGIN) the user. Returns the User; the view issues JWTs.

Guarantees:
- Codes are random (secrets module), hashed at rest, expire, are one-time use,
  and lock after OTP_MAX_ATTEMPTS wrong guesses.
- Only the newest OTP per (channel, identifier, purpose) is valid.
- REGISTER and LOGIN OTPs are not interchangeable: a login OTP can never
  create an account, a registration OTP can never log into one.
- The request endpoint responds identically whether or not an account exists.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.choices import OTPPurpose
from apps.accounts.exceptions import (
    AccountAlreadyExists,
    AccountDisabled,
    OTPAttemptsExceeded,
    OTPCooldown,
    OTPDeliveryFailed,
    OTPExpired,
    OTPInvalid,
)
from apps.accounts.identifiers import user_field_for
from apps.accounts.models import OTPChallenge, User
from apps.accounts.services.otp_delivery import (
    OTPDeliveryError,
    deliver_already_registered_notice,
    deliver_otp,
)
from apps.accounts.services.otp_rate_limit import reserve_otp_request

logger = logging.getLogger(__name__)


def generate_code(length: int | None = None) -> str:
    length = length or settings.OTP_LENGTH
    return f"{secrets.randbelow(10**length):0{length}d}"


def _active_challenges(channel: str, identifier: str, purpose: str):
    return OTPChallenge.objects.filter(
        channel=channel,
        identifier=identifier,
        purpose=purpose,
        consumed_at__isnull=True,
        invalidated_at__isnull=True,
    )


# ─────────────────────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────────────────────
def request_otp(
    *, channel: str, identifier: str, purpose: str, ip: str | None = None
) -> None:
    """
    Send an OTP if appropriate. Returns nothing on purpose: the caller must
    respond the same way whether a code was sent, a notice was sent, or
    nothing was sent, so the endpoint can't be used to find registered users.
    """
    reserve_otp_request(channel=channel, identifier=identifier, purpose=purpose)

    field = user_field_for(channel)
    # all_objects: a soft-deleted account still "owns" its email/phone.
    existing = User.all_objects.filter(**{field: identifier}).first()

    if purpose == OTPPurpose.REGISTER and existing is not None:
        try:
            deliver_already_registered_notice(channel=channel, to=identifier)
        except OTPDeliveryError:
            pass  # best effort: surfacing it would reveal the account exists
        return

    if purpose == OTPPurpose.LOGIN and (
        existing is None or existing.is_deleted or not existing.is_active
    ):
        return  # nothing to log in to: send nothing, say nothing

    issue_challenge(channel=channel, identifier=identifier, purpose=purpose, ip=ip)


def issue_challenge(
    *,
    channel: str,
    identifier: str,
    purpose: str,
    ip: str | None = None,
    context: dict | None = None,
) -> OTPChallenge:
    """
    Create a hashed OTP challenge and deliver the code. Callers must already
    have applied rate limits (reserve_otp_request) and decided a code is due.

    `context` binds extra facts to the challenge (e.g. which Google account a
    GOOGLE_LINK code is for); verification can require them to match.
    """
    code = generate_code()
    now = timezone.now()
    try:
        with transaction.atomic():
            # "Latest OTP wins": every older unused OTP stops working.
            _active_challenges(channel, identifier, purpose).update(invalidated_at=now)
            challenge = OTPChallenge.objects.create(
                channel=channel,
                identifier=identifier,
                purpose=purpose,
                code_hash=make_password(code),
                expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
                max_attempts=settings.OTP_MAX_ATTEMPTS,
                requested_ip=ip,
                context=context or {},
            )
    except IntegrityError:
        # A simultaneous request created the active OTP first (the DB's
        # one-active-OTP constraint caught the race).
        raise OTPCooldown(wait=settings.OTP_RESEND_COOLDOWN_SECONDS) from None

    try:
        deliver_otp(channel=channel, to=identifier, code=code, purpose=purpose)
    except OTPDeliveryError:
        # Never claim success for a code nobody received; kill the unusable OTP.
        OTPChallenge.objects.filter(pk=challenge.pk).update(
            invalidated_at=timezone.now()
        )
        raise OTPDeliveryFailed() from None

    logger.info(
        "OTP issued: challenge_id=%s purpose=%s channel=%s",
        challenge.pk,
        purpose,
        channel,
    )
    return challenge


# ─────────────────────────────────────────────────────────────
# Verify
# ─────────────────────────────────────────────────────────────
_OK, _INVALID, _EXPIRED, _LOCKED = "ok", "invalid", "expired", "locked"
_FAILURES = {_INVALID: OTPInvalid, _EXPIRED: OTPExpired, _LOCKED: OTPAttemptsExceeded}


def verify_otp(
    *,
    channel: str,
    identifier: str,
    purpose: str,
    code: str,
    context_match: dict | None = None,
    complete=None,
) -> User:
    """
    Check the code and return the authenticated user.

    - context_match: extra fields the challenge's `context` must have, e.g.
      {"google_sub": "..."}; a challenge issued for something else is
      simply not found (OTP_INVALID).
    - complete: function(challenge) -> User run after a correct code, inside
      the same transaction. Defaults to the REGISTER/LOGIN behaviour.

    Failure bookkeeping (attempt counts, invalidation) is committed before the
    error is raised: raising inside the transaction would roll back the
    attempt counter and give an attacker unlimited guesses.
    """
    lookup = {f"context__{key}": value for key, value in (context_match or {}).items()}
    with transaction.atomic():
        # Row lock: two simultaneous verifications of one OTP are serialised,
        # so an OTP can never be consumed twice or bypass the attempt limit.
        challenge = (
            _active_challenges(channel, identifier, purpose)
            .filter(**lookup)
            .select_for_update()
            .order_by("-created_at")
            .first()
        )
        outcome = _check_code(challenge, code)
        if outcome == _OK:
            # Same transaction: if creating/fetching the user fails, the OTP
            # consumption is rolled back too.
            user = (complete or _complete)(challenge)

    if outcome != _OK:
        logger.info("OTP verification failed: outcome=%s purpose=%s", outcome, purpose)
        raise _FAILURES[outcome]()

    logger.info("OTP verified: challenge_id=%s user_id=%s", challenge.pk, user.pk)
    return user


def _check_code(challenge: OTPChallenge | None, code: str) -> str:
    if challenge is None:
        return _INVALID

    now = timezone.now()
    if challenge.expires_at <= now:
        challenge.invalidated_at = now
        challenge.save(update_fields=["invalidated_at", "updated_at"])
        return _EXPIRED

    if not check_password(code, challenge.code_hash):
        challenge.attempts += 1
        fields = ["attempts", "updated_at"]
        if challenge.attempts >= challenge.max_attempts:
            challenge.invalidated_at = now
            fields.append("invalidated_at")
        challenge.save(update_fields=fields)
        return _LOCKED if challenge.invalidated_at else _INVALID

    challenge.consumed_at = now
    challenge.save(update_fields=["consumed_at", "updated_at"])
    return _OK


def _complete(challenge: OTPChallenge) -> User:
    field = user_field_for(challenge.channel)
    verified_field = f"{field}_verified_at"
    now = timezone.now()

    if challenge.purpose == OTPPurpose.REGISTER:
        if User.all_objects.filter(**{field: challenge.identifier}).exists():
            raise AccountAlreadyExists()
        try:
            # Role is never taken from the request: public sign-up is always STUDENT.
            return User.objects.create_user(
                **{field: challenge.identifier, verified_field: now},
                role=User.Role.STUDENT,
            )
        except (IntegrityError, DjangoValidationError):
            raise AccountAlreadyExists() from None

    # LOGIN
    user = User.objects.filter(**{field: challenge.identifier}).first()
    if user is None:
        raise OTPInvalid()  # account soft-deleted after the OTP was sent
    if not user.is_active:
        raise AccountDisabled()
    if getattr(user, verified_field) is None:
        setattr(user, verified_field, now)
        user.save(update_fields=[verified_field, "updated_at"])
    return user
