"""
JWT issuing, refresh rotation and revocation (patterns from Labe1's
session_tokens.py, SafeTokenRefreshSerializer and LogoutView).

Every token pair belongs to a UserSession via the `sid` claim.

Refresh rotation:
- Each refresh returns a NEW refresh token; the presented one is blacklisted.
- Concurrent refreshes with the same token (two tabs, a retry) are
  serialised with a row lock on the session. The loser gets the exact pair
  the winner produced, from a short-lived cache, instead of a false logout.
- Presenting an already-rotated refresh token AFTER that grace window means
  two parties hold the same token: the classic sign of a stolen refresh
  token. The whole session is revoked (refresh token reuse detection).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import (
    AuthenticationFailed,
    InvalidToken,
    TokenBackendError,
    TokenError,
)
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.exceptions import InvalidRefreshToken
from apps.accounts.models import User, UserSession
from apps.accounts.services.sessions import (
    SID_CLAIM,
    create_session,
    new_session_id,
    revoke_all_sessions,
    revoke_session,
    revoke_session_by_sid,
    token_expiry,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Issuing
# ─────────────────────────────────────────────────────────────
@transaction.atomic
def issue_tokens(user: User, *, ip=None, user_agent: str = "") -> dict:
    """
    Start a new session for a completed login and mint its token pair.

    `role` is a convenience claim for the frontend (e.g. which dashboard to
    show). The backend never trusts it: permission checks read the role from
    the database, so a role change applies immediately.
    """
    session_id = new_session_id()
    refresh = RefreshToken.for_user(user)  # also records an OutstandingToken
    refresh[SID_CLAIM] = session_id
    refresh["role"] = user.role
    create_session(
        user=user, refresh=refresh, session_id=session_id, ip=ip, user_agent=user_agent
    )
    update_last_login(None, user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# ─────────────────────────────────────────────────────────────
# Refresh (rotation)
# ─────────────────────────────────────────────────────────────
def _rotation_key(jti: str) -> str:
    return f"auth:refresh_rotation:{jti}"


def _remember_rotation(consumed_jti: str, data: dict) -> None:
    """Best effort: losing it only means a racing request gets a 401."""
    try:
        cache.set(
            _rotation_key(consumed_jti),
            data,
            timeout=settings.REFRESH_ROTATION_GRACE_SECONDS,
        )
    except Exception:
        logger.warning("Could not cache refresh rotation", exc_info=True)


def _recall_rotation(jti: str | None) -> dict | None:
    if not jti:
        return None
    try:
        return cache.get(_rotation_key(jti))
    except Exception:
        logger.warning("Could not read refresh rotation cache", exc_info=True)
        return None


def _no_active_account() -> AuthenticationFailed:
    return AuthenticationFailed(
        "No active session found for this token. Please log in again.",
        code="no_active_account",
    )


def rotate_refresh_token(raw_refresh: str) -> dict:
    try:
        # Verifies signature, expiry, token type and the blacklist.
        refresh = RefreshToken(raw_refresh)
    except TokenError:
        return _handle_rejected_refresh(raw_refresh)

    payload = refresh.payload
    user_id = payload.get(jwt_settings.USER_ID_CLAIM)
    session_id = payload.get(SID_CLAIM)
    consumed_jti = payload.get(jwt_settings.JTI_CLAIM)

    user = User.all_objects.filter(pk=user_id).first()
    if user is None or user.is_deleted or not user.is_active or not session_id:
        raise _no_active_account()

    reuse_detected = lifetime_exceeded = False
    with transaction.atomic():
        session = (
            UserSession.objects.select_for_update()
            .filter(session_id=session_id, user_id=user.pk)
            .first()
        )
        if session is None or not session.is_active:
            raise _no_active_account()

        if session.refresh_token_jti != consumed_jti:
            # Someone rotated this token while we waited for the lock.
            cached = _recall_rotation(consumed_jti)
            if cached is not None:
                return cached
            revoke_session(session, UserSession.RevokeReason.REFRESH_REUSE)
            reuse_detected = True
        elif timezone.now() - session.created_at > timedelta(
            days=settings.SESSION_MAX_LIFETIME_DAYS
        ):
            revoke_session(session, UserSession.RevokeReason.LIFETIME_EXCEEDED)
            lifetime_exceeded = True
        else:
            refresh.blacklist()
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh.outstand()
            data = {"access": str(refresh.access_token), "refresh": str(refresh)}

            session.refresh_token_jti = refresh[jwt_settings.JTI_CLAIM]
            session.last_active_at = timezone.now()
            session.expires_at = token_expiry(refresh)
            session.save(
                update_fields=[
                    "refresh_token_jti",
                    "last_active_at",
                    "expires_at",
                    "updated_at",
                ]
            )
            # Written inside the transaction: a request waiting on the row lock
            # only proceeds after commit, by which point this is readable.
            _remember_rotation(consumed_jti, data)

    # Raised after the transaction commits, so the revocation sticks.
    if reuse_detected:
        logger.warning(
            "Refresh token reuse detected; session revoked: user_id=%s", user.pk
        )
        raise _no_active_account()
    if lifetime_exceeded:
        raise AuthenticationFailed(
            "This session has reached its maximum lifetime. Please log in again.",
            code="session_expired",
        )
    return data


def _handle_rejected_refresh(raw_refresh: str) -> dict:
    """
    The token failed validation. If it is genuine and unexpired, the only
    remaining reason is that it is blacklisted, i.e. already rotated or
    logged out.
    """
    try:
        payload = token_backend.decode(raw_refresh, verify=True)
    except TokenBackendError:
        raise InvalidToken("Token is invalid or expired.") from None
    if payload.get("token_type") != "refresh":
        raise InvalidToken("Token is invalid or expired.")

    # Lost a race within the grace window: hand back the winner's pair.
    cached = _recall_rotation(payload.get(jwt_settings.JTI_CLAIM))
    if cached is not None:
        return cached

    # A rotated refresh token presented again after the grace window: two
    # parties hold it. Kill the session so the thief's copy dies too.
    session_id = payload.get(SID_CLAIM)
    if session_id:
        revoke_session_by_sid(session_id, UserSession.RevokeReason.REFRESH_REUSE)
        logger.warning(
            "Rotated refresh token reused; session revoked: user_id=%s",
            payload.get(jwt_settings.USER_ID_CLAIM),
        )
    raise InvalidToken("Token is invalid or expired.")


# ─────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────
def logout(
    user: User, *, session_id: str | None, raw_refresh: str | None = None
) -> None:
    """
    End the CURRENT session only (other devices stay logged in, as in Labe1).
    Revoking the session also blacklists its refresh token. If the client
    sends a refresh token, it must belong to this user.
    """
    if raw_refresh:
        try:
            payload = RefreshToken(raw_refresh, verify=False).payload
        except TokenError:
            payload = {}
        if payload and str(payload.get(jwt_settings.USER_ID_CLAIM)) != str(user.pk):
            raise InvalidRefreshToken("This refresh token does not belong to you.")

    if session_id:
        revoke_session_by_sid(session_id, UserSession.RevokeReason.LOGOUT)


def logout_everywhere(user: User) -> int:
    return revoke_all_sessions(user, UserSession.RevokeReason.LOGOUT_ALL)
