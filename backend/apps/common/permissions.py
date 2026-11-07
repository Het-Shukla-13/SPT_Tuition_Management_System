"""
Role-based permission classes (patterns from Labe1 Label_Auth app/permissions.py
and Labe1_Jango core/permissions/super_admin.py).

Rules:
- Roles are read from the database row loaded for this request, never from
  the JWT `role` claim (which is frontend convenience only).
- Fail closed: anything unexpected while deciding means "no".
- Every denial is logged (who, what, where) for the audit trail. Logging
  must never break the request, so it swallows its own errors.

Typical usage:
    permission_classes = [IsAdmin]                 # admin-only endpoint
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]  # per-object check
"""

import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

ADMIN_ROLE = "ADMIN"
STUDENT_ROLE = "STUDENT"


def _log_permission_denied(permission, request, message, obj=None) -> None:
    """Best-effort audit log for a permission denial. Never raises."""
    try:
        user = getattr(request, "user", None)
        logger.warning(
            "Permission denied: %s user_id=%s role=%s %s %s resource_id=%s",
            type(permission).__name__,
            getattr(user, "pk", None),
            getattr(user, "role", None),
            request.method,
            request.path,
            getattr(obj, "pk", None),
        )
    except Exception:
        logger.debug("Failed to log permission denial", exc_info=True)


def _is_authenticated(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated)


def has_role(user, role: str) -> bool:
    """Fails closed: a missing/unreadable role is never a match."""
    try:
        return bool(
            user and user.is_authenticated and user.is_active and user.role == role
        )
    except Exception:
        logger.warning("Role lookup failed; denying", exc_info=True)
        return False


class _RolePermission(BasePermission):
    required_role: str
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        if not _is_authenticated(request):
            return False  # DRF answers 401 for anonymous callers
        allowed = has_role(request.user, self.required_role)
        if not allowed:
            _log_permission_denied(self, request, self.message)
        return allowed


class IsAdmin(_RolePermission):
    """Institute administrators only."""

    required_role = ADMIN_ROLE
    message = "Administrator access required."


class IsStudent(_RolePermission):
    """Students only (e.g. the student portal's "my ..." endpoints)."""

    required_role = STUDENT_ROLE
    message = "Student access required."


class IsSuperUser(BasePermission):
    """
    The owner account(s) created with `createsuperuser`. Used for the most
    sensitive operations, such as granting or revoking ADMIN.
    """

    message = "Only the institute owner account can perform this action."

    def has_permission(self, request, view) -> bool:
        if not _is_authenticated(request):
            return False
        allowed = bool(
            request.user.is_active
            and request.user.is_superuser
            and request.user.role == ADMIN_ROLE
        )
        if not allowed:
            _log_permission_denied(self, request, self.message)
        return allowed


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level: admins may access any object; everyone else only objects
    they own. Prevents IDOR, e.g. a student changing /students/12/ to /13/.

    The owner is found via `view.owner_field` (default "user"), a dotted path
    such as "student.user". If the object IS a User, it must be the requester.
    """

    message = "You can only access your own records."

    def has_permission(self, request, view) -> bool:
        return _is_authenticated(request)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if has_role(user, ADMIN_ROLE):
            return True
        try:
            owner = self._resolve_owner(obj, getattr(view, "owner_field", "user"))
            allowed = owner is not None and owner.pk == user.pk
        except Exception:
            logger.warning("Owner lookup failed; denying", exc_info=True)
            allowed = False
        if not allowed:
            _log_permission_denied(self, request, self.message, obj=obj)
        return allowed

    @staticmethod
    def _resolve_owner(obj, owner_field: str):
        from django.contrib.auth import get_user_model

        if isinstance(obj, get_user_model()):
            return obj
        owner = obj
        for part in owner_field.split("."):
            owner = getattr(owner, part, None)
            if owner is None:
                return None
        return owner
