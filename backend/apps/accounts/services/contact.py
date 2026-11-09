"""
Account settings: add, change or remove the email/phone on an account
(spec 2.5 and 9.6), plus the admin recovery path for users who lost access.

Self-service change:
1. start_contact_change()    - a CONTACT_CHANGE code goes to the NEW address,
                               bound to this user (context user_id).
2. complete_contact_change() - correct code -> the new value is saved as
                               verified; the OLD address is told it changed.

Rules:
- An email/phone belongs to at most one account (soft-deleted ones included).
- An account always keeps at least one of email/phone (the DB enforces it too).
- Every change is audited in the same transaction.
- Changing contact details does not log out existing sessions. A Google link
  is unaffected: it is tied to the Google account id, not the email.
"""

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.exceptions import (
    AdminTargetRequiresOwner,
    CannotModifySelf,
    ContactInUse,
    ContactNotSet,
    ContactUnchanged,
    EmailRequiredWithoutSMS,
    LastContactMethod,
)
from apps.accounts.identifiers import mask_identifier, user_field_for
from apps.accounts.models import OTPChallenge, User
from apps.accounts.services.otp import issue_challenge, verify_otp
from apps.accounts.services.otp_delivery import (
    OTPDeliveryError,
    deliver_contact_changed_notice,
)
from apps.accounts.services.otp_rate_limit import reserve_otp_request
from apps.accounts.services.sms import sms_enabled
from apps.audit.models import AuditLog
from apps.audit.services import record

logger = logging.getLogger(__name__)

_LABEL = {OTPChannel.EMAIL: "email address", OTPChannel.PHONE: "phone number"}


def _other_channel(channel: str) -> str:
    return OTPChannel.PHONE if channel == OTPChannel.EMAIL else OTPChannel.EMAIL


def _ensure_free(field: str, value: str, owner: User) -> None:
    if User.all_objects.filter(**{field: value}).exclude(pk=owner.pk).exists():
        raise ContactInUse()


def _notify_old(channel: str, old_value: str | None, new_value: str | None) -> None:
    """Best effort, after commit: a failed notice must not undo the change."""
    if not old_value:
        return

    def send():
        try:
            deliver_contact_changed_notice(
                channel=channel,
                to=old_value,
                what=_LABEL[channel],
                new_value_masked=mask_identifier(channel, new_value)
                if new_value
                else None,
            )
        except OTPDeliveryError:
            logger.warning("Could not send contact-changed notice via %s", channel)

    transaction.on_commit(send)


# ─────────────────────────────────────────────────────────────
# Self-service add / change
# ─────────────────────────────────────────────────────────────
def start_contact_change(*, user: User, channel: str, identifier: str, ip=None) -> None:
    field = user_field_for(channel)
    if getattr(user, field) == identifier:
        raise ContactUnchanged()
    _ensure_free(field, identifier, user)

    reserve_otp_request(
        channel=channel, identifier=identifier, purpose=OTPPurpose.CONTACT_CHANGE
    )
    issue_challenge(
        channel=channel,
        identifier=identifier,
        purpose=OTPPurpose.CONTACT_CHANGE,
        ip=ip,
        context={"user_id": user.pk},
    )


def complete_contact_change(
    *, user: User, channel: str, identifier: str, code: str, ip=None
) -> User:
    field = user_field_for(channel)
    verified_field = f"{field}_verified_at"
    previous = {}

    def apply(challenge: OTPChallenge) -> User:
        locked = User.objects.select_for_update().get(pk=user.pk)
        _ensure_free(field, identifier, locked)  # someone may have taken it meanwhile
        previous["value"] = getattr(locked, field)

        setattr(locked, field, identifier)
        setattr(locked, verified_field, timezone.now())
        try:
            locked.save(update_fields=[field, verified_field, "updated_at"])
        except IntegrityError:
            raise ContactInUse() from None
        record(
            AuditLog.Action.CONTACT_CHANGED,
            actor=locked,
            target=locked,
            changes={field: [previous["value"], identifier], "verified": True},
            ip=ip,
        )
        _notify_old(channel, previous["value"], identifier)
        return locked

    # The code only works for THIS user: someone else can't finish the change
    # even if they somehow got the code.
    updated = verify_otp(
        channel=channel,
        identifier=identifier,
        purpose=OTPPurpose.CONTACT_CHANGE,
        code=code,
        context_match={"user_id": user.pk},
        complete=apply,
    )
    logger.info("Contact changed: user_id=%s field=%s", user.pk, field)
    return updated


def _ensure_can_remove(user: User, channel: str) -> None:
    """A login must keep a way to sign in: some contact, and an email while SMS is off."""
    if not getattr(user, user_field_for(_other_channel(channel))):
        raise LastContactMethod()
    if channel == OTPChannel.EMAIL and not sms_enabled():
        raise EmailRequiredWithoutSMS()


# ─────────────────────────────────────────────────────────────
# Self-service remove
# ─────────────────────────────────────────────────────────────
@transaction.atomic
def remove_contact(*, user: User, channel: str, ip=None) -> User:
    field = user_field_for(channel)
    locked = User.objects.select_for_update().get(pk=user.pk)
    old_value = getattr(locked, field)
    if not old_value:
        raise ContactNotSet()
    _ensure_can_remove(locked, channel)

    setattr(locked, field, None)
    setattr(locked, f"{field}_verified_at", None)
    locked.save(update_fields=[field, f"{field}_verified_at", "updated_at"])
    record(
        AuditLog.Action.CONTACT_REMOVED,
        actor=locked,
        target=locked,
        changes={field: [old_value, None]},
        ip=ip,
    )
    _notify_old(channel, old_value, None)
    return locked


# ─────────────────────────────────────────────────────────────
# Admin recovery (user lost access to their email/phone)
# ─────────────────────────────────────────────────────────────
@transaction.atomic
def admin_set_contact(
    *, actor: User, target: User, channel: str, identifier: str | None, ip=None
) -> User:
    """
    Set (or clear, with identifier=None) a user's email/phone on their behalf.
    A new value is stored UNVERIFIED; it becomes verified the first time the
    user logs in with an OTP sent to it.
    """
    if actor.pk == target.pk:
        raise CannotModifySelf("Use your account settings to change your own details.")
    locked = User.objects.select_for_update().get(pk=target.pk)
    if locked.is_admin and not actor.is_superuser:
        raise AdminTargetRequiresOwner()

    field = user_field_for(channel)
    verified_field = f"{field}_verified_at"
    old_value = getattr(locked, field)

    if identifier is None:
        if not old_value:
            raise ContactNotSet()
        _ensure_can_remove(locked, channel)
    else:
        if identifier == old_value:
            raise ContactUnchanged()
        _ensure_free(field, identifier, locked)

    setattr(locked, field, identifier)
    setattr(locked, verified_field, None)
    try:
        locked.save(update_fields=[field, verified_field, "updated_at"])
    except IntegrityError:
        raise ContactInUse() from None

    record(
        AuditLog.Action.CONTACT_CHANGED
        if identifier
        else AuditLog.Action.CONTACT_REMOVED,
        actor=actor,
        target=locked,
        changes={field: [old_value, identifier], "verified": False, "by_admin": True},
        ip=ip,
    )
    _notify_old(channel, old_value, identifier)
    logger.info(
        "Admin set contact: target_id=%s field=%s by actor_id=%s",
        locked.pk,
        field,
        actor.pk,
    )
    return locked
