"""JWT issuing and revocation (SimpleJWT), mirroring Labe1's session_tokens helpers."""

import logging

from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.exceptions import InvalidRefreshToken
from apps.accounts.models import User

logger = logging.getLogger(__name__)


def issue_tokens(user: User) -> dict:
    """
    Mint a fresh access/refresh pair for a completed login.

    `role` is added as a claim for the frontend's convenience (e.g. which
    dashboard to show). The backend NEVER trusts it for authorization:
    permission checks always read the role from the database, so a changed
    or revoked role takes effect immediately.
    """
    refresh = RefreshToken.for_user(user)  # also records it as an OutstandingToken
    refresh["role"] = user.role
    update_last_login(None, user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def revoke_refresh_token(user: User, raw_refresh: str) -> None:
    """
    Blacklist a refresh token on logout. Idempotent: an already blacklisted
    or expired token is simply "already logged out" (as in Labe1's LogoutView).
    A token belonging to someone else is rejected.
    """
    try:
        token = RefreshToken(raw_refresh)
    except TokenError:
        return  # already invalid: nothing left to revoke

    if str(token.get(jwt_settings.USER_ID_CLAIM)) != str(user.pk):
        raise InvalidRefreshToken("This refresh token does not belong to you.")

    try:
        token.blacklist()
    except TokenError:
        pass
    except Exception:
        logger.exception(
            "Unexpected error blacklisting refresh token for user_id=%s", user.pk
        )
        raise
