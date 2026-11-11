"""
Google Sign-In (spec 2.3 / 2.4): an emailed code the first time a Google
account is linked AND on every new device (Phase 1.5); one tap on a trusted
device.

Flow:
1. start_google_sign_in(id_token, device_token)
   - Linked to a user and this browser is trusted for them -> log in (tokens).
   - Linked, but a new device -> email a code to the account's email.
   - Not linked yet           -> email a code to the Google account's email.
   Both codes are bound to this Google account (`sub`).
2. complete_google_sign_in(id_token, code)
   - Code correct and issued for this Google account -> (link it to the
     invited user who owns that email, if not linked yet), log in; the view
     then trusts this device.

Invite-only: Google NEVER creates accounts. For an email with no account,
step 1 sends nothing but answers the same way.

Why the code: a Google account can carry an email address that its owner
doesn't actually control (non-Gmail addresses), so "the emails match" alone
is not proof. Only the real owner of the inbox can read the code.

Token verification uses Google's official library (as Labe1 does): checks the
signature against Google's published keys, expiry, issuer, and that the token
was issued for OUR client ID (`aud`), so tokens for other apps are rejected.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.exceptions import (
    AccountDisabled,
    GoogleAccountConflict,
    GoogleEmailNotVerified,
    GoogleNotConfigured,
    GoogleNotLinked,
    GoogleTokenInvalid,
    GoogleUnavailable,
    OTPInvalid,
)
from apps.accounts.identifiers import normalize_email
from apps.accounts.models import OTPChallenge, User
from apps.accounts.services.devices import is_trusted
from apps.accounts.services.otp import issue_challenge, verify_otp
from apps.accounts.services.otp_rate_limit import reserve_otp_request
from apps.audit.models import AuditLog
from apps.audit.services import record

logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str  # Google's stable, unique account id
    email: str


# ─────────────────────────────────────────────────────────────
# Token verification
# ─────────────────────────────────────────────────────────────
def verify_google_id_token(raw_token: str) -> GoogleIdentity:
    if not settings.GOOGLE_ALLOWED_AUDIENCES:
        logger.error("Google sign-in attempted but GOOGLE_OAUTH_CLIENT_ID is not set.")
        raise GoogleNotConfigured()

    try:
        payload = google_id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            audience=settings.GOOGLE_ALLOWED_AUDIENCES,
        )
    except google_exceptions.TransportError:
        logger.exception("Could not reach Google to verify an ID token.")
        raise GoogleUnavailable() from None
    except (ValueError, google_exceptions.GoogleAuthError):
        # Bad signature, expired, wrong audience/issuer, malformed...
        raise GoogleTokenInvalid() from None

    if payload.get("iss") not in GOOGLE_ISSUERS or not payload.get("sub"):
        raise GoogleTokenInvalid()
    if not payload.get("email"):
        raise GoogleTokenInvalid("This Google account did not share an email address.")
    if payload.get("email_verified") is not True:
        raise GoogleEmailNotVerified()

    try:
        email = normalize_email(payload["email"])
    except Exception:
        raise GoogleTokenInvalid() from None
    return GoogleIdentity(sub=str(payload["sub"]), email=email)


# ─────────────────────────────────────────────────────────────
# Step 1
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class GoogleStartResult:
    user: User | None  # set: already linked, log in now
    email: str  # where a code was (or would be) sent


def start_google_sign_in(
    *, raw_token: str, device_token: str | None = None, ip: str | None = None
) -> GoogleStartResult:
    identity = verify_google_id_token(raw_token)

    linked = User.all_objects.filter(google_id=identity.sub).first()
    if linked is not None:
        if linked.is_deleted or not linked.is_active:
            raise AccountDisabled()
        if is_trusted(linked, device_token):
            return GoogleStartResult(user=linked, email=identity.email)
        if not linked.email:
            raise GoogleNotLinked("This account has no email for the device check.")
        # New device: prove it with a code sent to the ACCOUNT's email.
        reserve_otp_request(
            channel=OTPChannel.EMAIL,
            identifier=linked.email,
            purpose=OTPPurpose.GOOGLE_LINK,
        )
        issue_challenge(
            channel=OTPChannel.EMAIL,
            identifier=linked.email,
            purpose=OTPPurpose.GOOGLE_LINK,
            ip=ip,
            context={"google_sub": identity.sub},
        )
        return GoogleStartResult(user=None, email=linked.email)

    # Not linked yet: prove ownership of the email with a code. Same limits
    # as every other OTP (cooldown, hourly cap, fail closed).
    reserve_otp_request(
        channel=OTPChannel.EMAIL,
        identifier=identity.email,
        purpose=OTPPurpose.GOOGLE_LINK,
    )
    owner = User.all_objects.filter(email=identity.email).first()
    if owner is None or owner.is_deleted or not owner.is_active:
        # Invite-only: Google never creates accounts (as in Labe1). Unknown,
        # disabled or deleted: send nothing, and answer exactly as if a code
        # was sent, so the response reveals nothing about the address.
        return GoogleStartResult(user=None, email=identity.email)

    issue_challenge(
        channel=OTPChannel.EMAIL,
        identifier=identity.email,
        purpose=OTPPurpose.GOOGLE_LINK,
        ip=ip,
        context={"google_sub": identity.sub},
    )
    return GoogleStartResult(user=None, email=identity.email)


# ─────────────────────────────────────────────────────────────
# Step 2
# ─────────────────────────────────────────────────────────────
def complete_google_sign_in(
    *, raw_token: str, code: str, ip: str | None = None
) -> User:
    # The same Google sign-in must finish the flow: the code is bound to this
    # Google account, so a code issued for a different one is "not found".
    identity = verify_google_id_token(raw_token)
    linked = User.all_objects.filter(google_id=identity.sub).first()

    def link(challenge: OTPChallenge) -> User:
        if linked is not None:
            return _already_linked(linked.pk)
        return _link(identity, ip=ip)

    return verify_otp(
        channel=OTPChannel.EMAIL,
        # A linked account's code went to the account's own email.
        identifier=linked.email
        if linked is not None and linked.email
        else identity.email,
        purpose=OTPPurpose.GOOGLE_LINK,
        code=code,
        context_match={"google_sub": identity.sub},
        complete=link,
    )


def _already_linked(user_id: int) -> User:
    """New-device check of an already-linked account: just re-check it's usable."""
    user = User.all_objects.select_for_update().filter(pk=user_id).first()
    if user is None or user.is_deleted:
        raise OTPInvalid()
    if not user.is_active:
        raise AccountDisabled()
    return user


def _link(identity: GoogleIdentity, *, ip: str | None) -> User:
    """Runs inside verify_otp's transaction, after the code was accepted."""
    now = timezone.now()

    other = User.all_objects.filter(google_id=identity.sub).first()
    owner = User.all_objects.select_for_update().filter(email=identity.email).first()

    if other is not None and other != owner:
        # Linked to someone else between step 1 and step 2.
        raise GoogleAccountConflict()

    if owner is None or owner.is_deleted:
        # No invited account with this email (removed after step 1).
        raise OTPInvalid()
    if not owner.is_active:
        raise AccountDisabled()
    if owner.google_id and owner.google_id != identity.sub:
        raise GoogleAccountConflict()

    if owner.google_id != identity.sub:
        owner.google_id = identity.sub
        owner.google_linked_at = now
        fields = ["google_id", "google_linked_at", "updated_at"]
        if owner.email_verified_at is None:
            owner.email_verified_at = now
            fields.append("email_verified_at")
        owner.save(update_fields=fields)
        record(AuditLog.Action.GOOGLE_LINKED, actor=owner, target=owner, ip=ip)
        logger.info("Google account linked: user_id=%s", owner.pk)
    return owner


# ─────────────────────────────────────────────────────────────
# Unlink
# ─────────────────────────────────────────────────────────────
@transaction.atomic
def unlink_google(*, user: User, ip: str | None = None) -> User:
    """
    Always safe: every Google-linked account has a verified email, so the
    user can still log in with email + password (or set one with an emailed
    code). Existing sessions stay valid. The next Google sign-in will need an
    email code again.
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.google_id:
        raise GoogleNotLinked()
    user.google_id = None
    user.google_linked_at = None
    user.save(update_fields=["google_id", "google_linked_at", "updated_at"])
    record(AuditLog.Action.GOOGLE_UNLINKED, actor=user, target=user, ip=ip)
    return user
