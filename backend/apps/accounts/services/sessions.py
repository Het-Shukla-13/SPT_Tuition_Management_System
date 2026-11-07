"""
Login sessions: create, check, revoke (pattern from Labe1's utils/session.py).

Differences from Labe1, on purpose:
- No Redis fast path. Labe1 checks Redis first because many services verify
  sessions on every request. We are one service and our cache is PostgreSQL
  anyway, so a direct indexed lookup is both simpler and just as fast.
- Revoking a session also blacklists its current refresh token, so the
  refresh token can't be used even if session checks were ever bypassed.
"""

import logging
import uuid
from datetime import UTC, datetime

from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import User, UserSession

logger = logging.getLogger(__name__)

# JWT claim carrying the session id. Lives here (not in tokens.py) because the
# authentication class imports it while DRF is still loading, and this module
# must not pull in anything that imports rest_framework.views.
SID_CLAIM = "sid"


def new_session_id() -> str:
    return uuid.uuid4().hex


def token_expiry(token) -> datetime:
    return datetime.fromtimestamp(token["exp"], tz=UTC)


def create_session(
    *, user: User, refresh, session_id: str, ip=None, user_agent=""
) -> UserSession:
    return UserSession.objects.create(
        user=user,
        session_id=session_id,
        refresh_token_jti=refresh["jti"],
        expires_at=token_expiry(refresh),
        ip_address=ip,
        user_agent=user_agent or "",
    )


def is_session_active(user_id, session_id: str) -> bool:
    return (
        UserSession.objects.active()
        .filter(session_id=session_id, user_id=user_id)
        .exists()
    )


def blacklist_jti(jti: str) -> None:
    """Blacklist a refresh token by its jti. No-op if unknown or already blacklisted."""
    outstanding = OutstandingToken.objects.filter(jti=jti).first()
    if outstanding is not None:
        BlacklistedToken.objects.get_or_create(token=outstanding)


def revoke_sessions(queryset, reason: str) -> int:
    """Revoke every still-open session in `queryset`. Returns how many were revoked."""
    now = timezone.now()
    sessions = list(queryset.filter(revoked_at__isnull=True))
    for session in sessions:
        blacklist_jti(session.refresh_token_jti)
    count = queryset.filter(pk__in=[s.pk for s in sessions]).update(
        revoked_at=now, revoked_reason=reason, updated_at=now
    )
    if count:
        logger.info("Revoked %s session(s): reason=%s", count, reason)
    return count


def revoke_session(session: UserSession, reason: str) -> None:
    revoke_sessions(UserSession.objects.filter(pk=session.pk), reason)


def revoke_session_by_sid(session_id: str, reason: str) -> None:
    revoke_sessions(UserSession.objects.filter(session_id=session_id), reason)


def revoke_all_sessions(user: User, reason: str) -> int:
    return revoke_sessions(UserSession.objects.filter(user=user), reason)
