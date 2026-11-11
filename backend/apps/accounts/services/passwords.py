"""
Email + password login with an emailed code on new devices (Phase 1.5).
Design: docs/plans/phase-1-5-password-login.md.

login_with_password()      password check -> logged in (trusted device) or a code
resend_new_device_code()   another code for the same pending login
verify_new_device()        code check -> logged in (the view then trusts the device)
request_password_code()    first password / forgot password: email a code
reset_password()           code + new password -> logged in, everything else ended
change_password()          logged in: current + new password

Guarantees:
- One generic INVALID_CREDENTIALS for every failed login, and a dummy hash
  check when there's no account, so neither the message nor the timing
  reveals who has an account.
- Too many wrong passwords for an email lock it for a while (counted per
  email, so unknown emails lock the same way).
- A new-device code only works together with the login ticket returned to the
  browser that typed the correct password.
"""

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.exceptions import (
    AccountDisabled,
    InvalidCredentials,
    LoginLocked,
    LoginTicketInvalid,
    OTPCooldown,
    OTPInvalid,
    WrongPassword,
)
from apps.accounts.identifiers import mask_email
from apps.accounts.models import OTPChallenge, TrustedDevice, User, UserSession
from apps.accounts.services.devices import is_trusted, revoke_trusted_devices
from apps.accounts.services.otp import issue_challenge, request_otp, verify_otp
from apps.accounts.services.otp_rate_limit import reserve_otp_request
from apps.accounts.services.sessions import revoke_sessions
from apps.audit.models import AuditLog
from apps.audit.services import record

logger = logging.getLogger(__name__)

TICKET_SALT = "accounts.login-ticket"


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A real hash of a random password: checking against it costs the same time."""
    return make_password(secrets.token_urlsafe(16))


# ─────────────────────────────────────────────────────────────
# Lockout (per email, in the shared cache)
# ─────────────────────────────────────────────────────────────
def _key(kind: str, email: str) -> str:
    return f"auth:login_{kind}:{hashlib.sha256(email.encode()).hexdigest()}"


def _ensure_not_locked(email: str) -> None:
    try:
        locked_at = cache.get(_key("lock", email))
    except Exception:
        # Fail open here: the per-IP throttle (fail closed) still limits guessing.
        logger.warning("Login lockout store unavailable", exc_info=True)
        return
    if locked_at is not None:
        remaining = settings.LOGIN_LOCKOUT_SECONDS - int(time.time() - locked_at)
        raise LoginLocked(wait=max(1, remaining))


def _record_failure(email: str) -> None:
    try:
        key = _key("fail", email)
        cache.add(key, 0, timeout=settings.LOGIN_LOCKOUT_SECONDS)
        if cache.incr(key) >= settings.LOGIN_MAX_FAILURES:
            cache.set(
                _key("lock", email), time.time(), timeout=settings.LOGIN_LOCKOUT_SECONDS
            )
            cache.delete(key)
            logger.warning("Login locked after repeated wrong passwords")
    except Exception:
        logger.warning("Could not record a failed login", exc_info=True)


def _clear_failures(email: str) -> None:
    try:
        cache.delete_many([_key("fail", email), _key("lock", email)])
    except Exception:
        logger.warning("Could not clear login failures", exc_info=True)


# ─────────────────────────────────────────────────────────────
# Login tickets
# ─────────────────────────────────────────────────────────────
def _make_ticket(user: User, nonce: str) -> str:
    return signing.dumps({"u": user.pk, "n": nonce}, salt=TICKET_SALT, compress=True)


def _read_ticket(ticket: str) -> tuple[User, str]:
    try:
        data = signing.loads(
            ticket, salt=TICKET_SALT, max_age=settings.LOGIN_TICKET_MAX_AGE_SECONDS
        )
    except signing.BadSignature:  # includes SignatureExpired
        raise LoginTicketInvalid() from None
    user = User.objects.filter(pk=data.get("u")).first()
    if user is None or not user.email or not data.get("n"):
        raise LoginTicketInvalid()
    return user, data["n"]


# ─────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LoginResult:
    user: User | None  # set: logged in now (trusted device)
    ticket: str | None = None  # set: a new-device code was emailed
    masked_email: str | None = None


def login_with_password(
    *, email: str, password: str, device_token: str | None, ip: str | None = None
) -> LoginResult:
    _ensure_not_locked(email)

    user = User.all_objects.filter(email=email).first()
    usable = user is not None and not user.is_deleted and user.has_usable_password()
    if usable:
        correct = user.check_password(password)
    else:
        check_password(password, _dummy_hash())  # same cost as a real check
        correct = False
    if not correct:
        _record_failure(email)
        raise InvalidCredentials()

    _clear_failures(email)
    if not user.is_active:
        raise AccountDisabled()
    if is_trusted(user, device_token):
        return LoginResult(user=user)

    nonce = secrets.token_urlsafe(16)
    _send_new_device_code(user, nonce, ip=ip)
    return LoginResult(
        user=None, ticket=_make_ticket(user, nonce), masked_email=mask_email(user.email)
    )


def _send_new_device_code(user: User, nonce: str, *, ip: str | None) -> None:
    try:
        reserve_otp_request(
            channel=OTPChannel.EMAIL,
            identifier=user.email,
            purpose=OTPPurpose.NEW_DEVICE,
        )
    except OTPCooldown:
        # Logged in again within the resend cooldown (e.g. the page was
        # reloaded): the code already in the inbox now belongs to THIS browser.
        pending = (
            OTPChallenge.objects.filter(
                channel=OTPChannel.EMAIL,
                identifier=user.email,
                purpose=OTPPurpose.NEW_DEVICE,
                consumed_at__isnull=True,
                invalidated_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )
        if pending is None:
            raise
        pending.context = {**pending.context, "ticket": nonce}
        pending.save(update_fields=["context", "updated_at"])
        return
    issue_challenge(
        channel=OTPChannel.EMAIL,
        identifier=user.email,
        purpose=OTPPurpose.NEW_DEVICE,
        ip=ip,
        context={"ticket": nonce},
    )


def resend_new_device_code(*, ticket: str, ip: str | None = None) -> str:
    """Email a fresh code for the same pending login. Returns the masked email."""
    user, nonce = _read_ticket(ticket)
    if not user.is_active:
        raise LoginTicketInvalid()
    reserve_otp_request(
        channel=OTPChannel.EMAIL, identifier=user.email, purpose=OTPPurpose.NEW_DEVICE
    )
    issue_challenge(
        channel=OTPChannel.EMAIL,
        identifier=user.email,
        purpose=OTPPurpose.NEW_DEVICE,
        ip=ip,
        context={"ticket": nonce},
    )
    return mask_email(user.email)


def verify_new_device(*, ticket: str, code: str) -> User:
    user, nonce = _read_ticket(ticket)
    return verify_otp(
        channel=OTPChannel.EMAIL,
        identifier=user.email,
        purpose=OTPPurpose.NEW_DEVICE,
        code=code,
        context_match={"ticket": nonce},
        complete=lambda challenge: _active_with_verified_email(user.pk),
    )


def _active_with_verified_email(user_id: int) -> User:
    """Runs inside verify_otp's transaction after a correct code."""
    user = User.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        raise OTPInvalid()
    if not user.is_active:
        raise AccountDisabled()
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
    return user


# ─────────────────────────────────────────────────────────────
# First password / forgot password
# ─────────────────────────────────────────────────────────────
def request_password_code(*, email: str, ip: str | None = None) -> None:
    """Same contract as a login OTP request: identical answer whether or not the email exists."""
    request_otp(
        channel=OTPChannel.EMAIL,
        identifier=email,
        purpose=OTPPurpose.SET_PASSWORD,
        ip=ip,
    )


def _validate_new_password(password: str, user: User | None) -> None:
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": exc.messages}) from None


def reset_password(
    *, email: str, code: str, new_password: str, ip: str | None = None
) -> User:
    """
    Set a new password after proving the inbox. A reset means the old password
    may be known to someone else, so EVERY session and trusted device ends.
    The caller logs this browser in and trusts it (the code just proved it).
    """
    # Check the password first, so a weak password doesn't use up the code.
    _validate_new_password(new_password, User.objects.filter(email=email).first())

    def complete(challenge: OTPChallenge) -> User:
        user = _active_with_verified_email_by_email(email)
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoke_sessions(
            UserSession.objects.filter(user=user),
            UserSession.RevokeReason.PASSWORD_CHANGED,
        )
        revoke_trusted_devices(user, TrustedDevice.RevokeReason.PASSWORD_RESET)
        record(AuditLog.Action.PASSWORD_SET, actor=user, target=user, ip=ip)
        return user

    user = verify_otp(
        channel=OTPChannel.EMAIL,
        identifier=email,
        purpose=OTPPurpose.SET_PASSWORD,
        code=code,
        complete=complete,
    )
    _clear_failures(email)
    logger.info("Password set via emailed code: user_id=%s", user.pk)
    return user


def _active_with_verified_email_by_email(email: str) -> User:
    user = User.objects.select_for_update().filter(email=email).first()
    if user is None:
        raise OTPInvalid()
    return _active_with_verified_email(user.pk)


# ─────────────────────────────────────────────────────────────
# Change password (logged in)
# ─────────────────────────────────────────────────────────────
@transaction.atomic
def change_password(
    *,
    user: User,
    current_password: str,
    new_password: str,
    session_id: str | None,
    device_token: str | None,
    ip: str | None = None,
) -> None:
    """
    Other sessions end and other devices need a code again; this session and
    this device stay as they are.
    """
    if user.email:
        _ensure_not_locked(user.email)
    if not user.has_usable_password():
        raise WrongPassword(
            'You don\'t have a password yet. Use "Set or reset password" on the login page.'
        )
    if not user.check_password(current_password):
        if user.email:
            _record_failure(user.email)
        raise WrongPassword()
    _validate_new_password(new_password, user)

    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    others = UserSession.objects.filter(user=user)
    if session_id:
        others = others.exclude(session_id=session_id)
    revoke_sessions(others, UserSession.RevokeReason.PASSWORD_CHANGED)
    revoke_trusted_devices(
        user, TrustedDevice.RevokeReason.PASSWORD_CHANGED, keep_token=device_token
    )
    record(AuditLog.Action.PASSWORD_CHANGED, actor=user, target=user, ip=ip)
