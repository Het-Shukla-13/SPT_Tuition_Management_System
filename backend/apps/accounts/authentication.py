"""
JWT authentication that also enforces sessions
(pattern from Labe1's SingleSessionJWTAuthentication).

On top of SimpleJWT's checks (signature, expiry, issuer/audience, active
user), every request's token must carry a `sid` whose UserSession is still
active. That is what makes logout, "log out of all devices" and session
revocation take effect immediately, instead of when the access token expires.
"""

import logging

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings

# Only lightweight imports here: DRF imports this module while loading its own
# views, so anything that imports rest_framework.views would be circular.
from apps.accounts.services.sessions import SID_CLAIM, is_session_active

logger = logging.getLogger(__name__)


class SessionJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        user_id = token.get(jwt_settings.USER_ID_CLAIM)
        session_id = token.get(SID_CLAIM)

        if not session_id:
            logger.warning("JWT rejected: no sid claim (user_id=%s)", user_id)
            raise InvalidToken("Please log in again.")

        if not is_session_active(user_id, session_id):
            logger.info("JWT rejected: session ended (user_id=%s)", user_id)
            raise InvalidToken("This session has ended. Please log in again.")

        return token


class SessionJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tells Swagger this is a Bearer-JWT scheme (enables the Authorize button)."""

    target_class = "apps.accounts.authentication.SessionJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
