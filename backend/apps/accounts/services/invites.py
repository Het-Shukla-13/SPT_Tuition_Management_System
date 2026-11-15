"""
Invite links: the one-click "Set your password" link in an invite email.

- Single use, expires after INVITE_LINK_TTL_DAYS, stored only as a SHA-256 hash.
- Sending a new invite cancels the person's older links.
- Accepting sets the password and confirms the email (the link proved the inbox).
- Any first login (password, emailed code or Google) also marks the link used,
  so an old link can't be replayed later.
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.exceptions import AccountDisabled, InviteLinkInvalid
from apps.accounts.models import InviteLink, User
from apps.audit.models import AuditLog
from apps.audit.services import record


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def invite_url(raw: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/set-password?token={raw}"


def create_invite_link(user: User) -> str:
    """A fresh link for `user` (older unused ones are cancelled). Returns the raw token."""
    now = timezone.now()
    InviteLink.objects.filter(
        user=user, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now)
    raw = secrets.token_urlsafe(32)
    InviteLink.objects.create(
        user=user,
        token_hash=_hash(raw),
        expires_at=now + timedelta(days=settings.INVITE_LINK_TTL_DAYS),
    )
    return raw


def _usable_link(raw: str, *, lock: bool = False) -> InviteLink:
    queryset = InviteLink.objects.select_related("user")
    if lock:
        queryset = queryset.select_for_update()
    link = queryset.filter(token_hash=_hash(raw or "")).first()
    # One generic answer for unknown / used / cancelled / expired, so the
    # endpoint can't be used to learn anything about a token.
    if link is None or not link.is_usable or not link.user.email:
        raise InviteLinkInvalid()
    if not link.user.is_active:
        raise AccountDisabled()
    return link


def check_invite_link(raw: str) -> User:
    """Who the link is for (to greet them on the Set password screen)."""
    return _usable_link(raw).user


@transaction.atomic
def accept_invite(*, raw: str, new_password: str, ip=None) -> User:
    """Set the first password through the link and use the link up."""
    from apps.accounts.services.passwords import validate_new_password

    link = _usable_link(raw, lock=True)
    user = User.objects.select_for_update().get(pk=link.user_id)
    validate_new_password(new_password, user)
    now = timezone.now()
    user.set_password(new_password)
    fields = ["password", "updated_at"]
    if user.email_verified_at is None:
        user.email_verified_at = now
        fields.append("email_verified_at")
    user.save(update_fields=fields)
    link.used_at = now
    link.save(update_fields=["used_at", "updated_at"])
    record(AuditLog.Action.INVITE_ACCEPTED, actor=user, target=user, ip=ip)
    return user


def use_up_invite_links(user: User) -> None:
    """The person has logged in some other way: their invite link is spent."""
    InviteLink.objects.filter(
        user=user, used_at__isnull=True, revoked_at__isnull=True
    ).update(used_at=timezone.now())
