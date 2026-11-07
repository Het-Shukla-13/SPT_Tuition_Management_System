"""
Administrative actions on user accounts: activate, deactivate, change role.

Rules (spec section 10.2):
- Nobody can change their own role or deactivate themselves.
- Only the owner (superuser) can act on another ADMIN, or grant/revoke ADMIN.
- The last active ADMIN can never be demoted or deactivated.
- Deactivating or changing a role ends all of that user's sessions at once,
  so the change applies on every device immediately.
- Every change is written to the audit log in the same transaction.
"""

import logging

from django.db import transaction

from apps.accounts.exceptions import (
    AdminTargetRequiresOwner,
    CannotModifySelf,
    LastAdminProtected,
)
from apps.accounts.models import User, UserSession
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
