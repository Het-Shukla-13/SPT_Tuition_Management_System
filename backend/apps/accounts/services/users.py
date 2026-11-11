"""
Administrative actions on user accounts: create (invite), activate,
deactivate, change role, edit name.

Rules (spec section 10.2):
- Nobody can change their own role or deactivate themselves.
- Only the owner (superuser) can act on another ADMIN, or grant/revoke ADMIN.
- The last active ADMIN can never be demoted or deactivated.
- Deactivating or changing a role ends all of that user's sessions at once,
  so the change applies on every device immediately.
- Every change is written to the audit log in the same transaction.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.accounts.choices import OTPChannel
from apps.accounts.exceptions import (
    AccountDisabled,
    AdminTargetRequiresOwner,
    CannotModifySelf,
    ContactInUse,
    InviteAlreadyAccepted,
    LastAdminProtected,
)
from apps.accounts.models import TrustedDevice, User, UserSession
from apps.accounts.services.devices import revoke_trusted_devices
from apps.accounts.services.otp_delivery import OTPDeliveryError, deliver_invite
from apps.accounts.services.sessions import revoke_all_sessions
from apps.audit.models import AuditLog
from apps.audit.services import record

logger = logging.getLogger(__name__)


def _lock(user: User) -> User:
    return User.objects.select_for_update().get(pk=user.pk)


def _ensure_not_self(actor: User, target: User) -> None:
    if actor.pk == target.pk:
        raise CannotModifySelf()


def _ensure_may_touch_admin(actor: User, target: User) -> None:
    if target.is_admin and not actor.is_superuser:
        raise AdminTargetRequiresOwner()


def _ensure_other_active_admin_exists(target: User) -> None:
    # Lock all active admins so two simultaneous demotions can't both pass
    # this check and leave the institute with no administrator.
    other_admins = (
        User.objects.select_for_update()
        .filter(role=User.Role.ADMIN, is_active=True)
        .exclude(pk=target.pk)
    )
    if not list(other_admins):
        raise LastAdminProtected()


@transaction.atomic
def deactivate_user(*, actor: User, target: User, ip: str | None = None) -> User:
    target = _lock(target)
    _ensure_not_self(actor, target)
    _ensure_may_touch_admin(actor, target)
    if not target.is_active:
        return target  # idempotent
    if target.is_admin:
        _ensure_other_active_admin_exists(target)

    target.is_active = False
    target.save(update_fields=["is_active", "updated_at"])
    revoke_all_sessions(target, UserSession.RevokeReason.ACCOUNT_DEACTIVATED)
    revoke_trusted_devices(target, TrustedDevice.RevokeReason.ACCOUNT_DEACTIVATED)
    record(
        AuditLog.Action.USER_DEACTIVATED,
        actor=actor,
        target=target,
        changes={"is_active": [True, False]},
        ip=ip,
    )
    logger.info("User deactivated: target_id=%s by actor_id=%s", target.pk, actor.pk)
    return target


@transaction.atomic
def activate_user(*, actor: User, target: User, ip: str | None = None) -> User:
    target = _lock(target)
    _ensure_not_self(actor, target)
    _ensure_may_touch_admin(actor, target)
    if target.is_active:
        return target  # idempotent

    target.is_active = True
    target.save(update_fields=["is_active", "updated_at"])
    record(
        AuditLog.Action.USER_ACTIVATED,
        actor=actor,
        target=target,
        changes={"is_active": [False, True]},
        ip=ip,
    )
    logger.info("User activated: target_id=%s by actor_id=%s", target.pk, actor.pk)
    return target


@transaction.atomic
def change_role(*, actor: User, target: User, role: str, ip: str | None = None) -> User:
    """Grant or revoke ADMIN. Callers must already have checked IsSuperUser."""
    target = _lock(target)
    _ensure_not_self(actor, target)
    if target.role == role:
        return target  # idempotent
    if target.is_admin and target.is_active:
        _ensure_other_active_admin_exists(target)

    old_role = target.role
    target.role = role
    target.save(update_fields=["role", "updated_at"])
    revoke_all_sessions(target, UserSession.RevokeReason.ROLE_CHANGED)
    revoke_trusted_devices(target, TrustedDevice.RevokeReason.ROLE_CHANGED)
    record(
        AuditLog.Action.USER_ROLE_CHANGED,
        actor=actor,
        target=target,
        changes={"role": [old_role, role]},
        ip=ip,
    )
    logger.info(
        "User role changed: target_id=%s %s->%s by actor_id=%s",
        target.pk,
        old_role,
        role,
        actor.pk,
    )
    return target


# ─────────────────────────────────────────────────────────────
# Creating logins (invite-only platform)
# ─────────────────────────────────────────────────────────────
def _ensure_contact_free(*, email: str | None, phone: str | None) -> None:
    errors = {}
    if email and User.all_objects.filter(email=email).exists():
        errors["email"] = ["Another login already uses this email."]
    if phone and User.all_objects.filter(phone=phone).exists():
        errors["phone"] = ["Another login already uses this phone number."]
    if errors:
        raise ContactInUse(details=errors)


def send_invite(user: User) -> dict:
    """
    Tell the person their login exists, on every contact it has. Best effort:
    a failed SMS/email doesn't undo the login (the admin can resend).
    Returns {"email": bool, "phone": bool} for the channels attempted.
    """
    results = {}
    targets = [(OTPChannel.EMAIL, user.email), (OTPChannel.PHONE, user.phone)]
    for channel, to in targets:
        if not to:
            continue
        try:
            deliver_invite(
                channel=channel,
                to=to,
                first_name=user.first_name or "there",
                role_label=User.Role(user.role).label.lower(),
            )
            results[channel.lower()] = True
        except OTPDeliveryError:
            results[channel.lower()] = False
    return results


def invite_user(
    *,
    actor: User,
    first_name: str,
    last_name: str,
    role: str,
    email: str | None = None,
    phone: str | None = None,
    ip: str | None = None,
) -> tuple[User, dict]:
    """
    Create a login and send the invite. Only the owner may create ADMINs.
    The person then logs in with an OTP (or Google) to this email/phone.
    """
    with transaction.atomic():
        user = create_login(
            actor=actor,
            first_name=first_name,
            last_name=last_name,
            role=role,
            email=email,
            phone=phone,
            ip=ip,
        )
    return user, send_invite(user)


def create_login(
    *,
    actor: User,
    first_name: str,
    last_name: str,
    role: str,
    email: str | None = None,
    phone: str | None = None,
    ip: str | None = None,
) -> User:
    """
    Create the login row without messaging anyone. Callers run it inside their
    transaction and call send_invite() only after it commits, so a rolled-back
    admission never sends an invite for a login that doesn't exist.
    """
    if role == User.Role.ADMIN and not actor.is_superuser:
        raise AdminTargetRequiresOwner(
            "Only the institute owner account can add administrators."
        )
    _ensure_contact_free(email=email, phone=phone)
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                role=role,
                invited_by=actor,
            )
    except (IntegrityError, DjangoValidationError):
        raise ContactInUse() from None
    record(
        AuditLog.Action.USER_INVITED,
        actor=actor,
        target=user,
        changes={"role": role, "email": email, "phone": phone},
        ip=ip,
    )
    logger.info(
        "Login created: user_id=%s role=%s by actor_id=%s", user.pk, role, actor.pk
    )
    return user


def resend_invite(*, actor: User, target: User) -> dict:
    if target.activated_at is not None:
        raise InviteAlreadyAccepted()
    if not target.is_active:
        raise AccountDisabled()
    return send_invite(target)


@transaction.atomic
def update_user_details(
    *, actor: User, target: User, first_name: str | None, last_name: str | None, ip=None
) -> User:
    """Change a login's name (self-service, or an admin fixing it)."""
    locked = User.objects.select_for_update().get(pk=target.pk)
    if actor.pk != locked.pk:
        _ensure_may_touch_admin(actor, locked)
    changes = {}
    for field, value in (("first_name", first_name), ("last_name", last_name)):
        if value is not None and value != getattr(locked, field):
            changes[field] = [getattr(locked, field), value]
            setattr(locked, field, value)
    if changes:
        locked.save(update_fields=[*changes, "updated_at"])
        record(
            AuditLog.Action.USER_UPDATED,
            actor=actor,
            target=locked,
            changes=changes,
            ip=ip,
        )
    return locked
