"""
Authentication endpoints. Views stay thin: validate input, call a service,
shape the response. All decisions live in apps/accounts/services/.
"""

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import APIException, NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import TrustedDevice, UserSession
from apps.accounts.serializers import (
    AuthTokensSerializer,
    LogoutSerializer,
    NameUpdateSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    TokenPairSerializer,
    TokenRefreshSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from apps.accounts.services.auth_cookies import (
    clear_device_cookie,
    clear_refresh_cookie,
    refresh_from_request,
    token_response,
)
from apps.accounts.services.devices import revoke_trusted_devices
from apps.accounts.services.otp import request_otp, verify_otp
from apps.accounts.services.sessions import SID_CLAIM, revoke_session
from apps.accounts.services.tokens import (
    issue_tokens,
    logout,
    logout_everywhere,
    rotate_refresh_token,
)
from apps.accounts.services.users import update_user_details
from apps.common.request_utils import client_ip, user_agent
from apps.common.responses import ApiResponse
from apps.common.throttling import ResilientScopedRateThrottle

AUTH_TAG = ["Auth"]
SESSIONS_TAG = ["Auth: sessions"]


def _current_session_id(request) -> str | None:
    return request.auth.get(SID_CLAIM) if request.auth is not None else None


class OTPRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=AUTH_TAG,
        summary="Request a login code (phone only)",
        description=(
            "Phone login: an SMS code every time. Email logins use `login/` (password) "
            "and get `EMAIL_LOGIN_NEEDS_PASSWORD` here.\n\n"
            "Invite-only: accounts are created by the institute, never here. Sends a "
            "one-time login code if this phone has an active account; for any "
            "other address nothing is sent, and the response is identical either way, "
            "so this endpoint can't be used to discover who has an account.\n\n"
            "Limits: one request per identifier per cooldown period, a cap per hour, "
            "and a per-IP limit."
        ),
        request=OTPRequestSerializer,
        responses={
            200: OpenApiResponse(description="Request accepted."),
            400: OpenApiResponse(description="VALIDATION_ERROR"),
            429: OpenApiResponse(
                description="OTP_COOLDOWN / OTP_REQUEST_LIMIT_REACHED / THROTTLED"
            ),
            503: OpenApiResponse(
                description="OTP_DELIVERY_FAILED / OTP_TEMPORARILY_UNAVAILABLE"
            ),
        },
    )
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_otp(**serializer.validated_data, ip=client_ip(request))
        return ApiResponse.success(
            message="If the details are valid, a verification code has been sent.",
            data={
                "expires_in_seconds": settings.OTP_TTL_SECONDS,
                "resend_after_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
            },
        )


class OTPVerifyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(
        tags=AUTH_TAG,
        summary="Verify an OTP and receive JWT tokens",
        description=(
            "Logs into the existing account and returns access + refresh tokens. "
            "The first successful login activates an invited account."
        ),
        request=OTPVerifySerializer,
        responses={
            200: AuthTokensSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR / OTP_INVALID / OTP_EXPIRED"
            ),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            429: OpenApiResponse(description="OTP_ATTEMPTS_EXCEEDED / THROTTLED"),
        },
    )
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_otp(**serializer.validated_data)
        tokens = issue_tokens(
            user, ip=client_ip(request), user_agent=user_agent(request)
        )
        return token_response(
            message="Verified successfully.",
            tokens=tokens,
            extra={"user": UserSerializer(user).data},
        )


class TokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        # Without an auth scheme DRF turns 401 (AuthenticationFailed) into 403.
        # A dead refresh token is "log in again" (401), not "forbidden" (403).
        return 'Bearer realm="api"'

    @extend_schema(
        tags=AUTH_TAG,
        summary="Refresh the access token (rotates the refresh token)",
        description=(
            "Returns a new access token AND a new refresh token; the presented "
            "refresh token stops working. Two refreshes with the same token within "
            "a short grace window (e.g. two tabs) both receive the same new pair. "
            "Re-using an old refresh token after that window ends the whole session "
            "(theft protection).\n\n"
            "Browsers: send no body; the refresh token is read from the HttpOnly "
            "login cookie, and the `X-Requested-With` header is required. The new "
            "refresh token is set as the cookie again."
        ),
        request=TokenRefreshSerializer,
        responses={
            200: TokenPairSerializer,
            401: OpenApiResponse(
                description="TOKEN_NOT_VALID / NO_ACTIVE_ACCOUNT / SESSION_EXPIRED"
            ),
        },
    )
    def post(self, request):
        try:
            serializer = TokenRefreshSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            raw = refresh_from_request(
                request, serializer.validated_data.get("refresh")
            )
            if not raw:
                raise NotAuthenticated("No refresh token: please log in.")
            tokens = rotate_refresh_token(raw)
        except APIException as exc:
            response = self.handle_exception(exc)
            if response.status_code == 401:
                clear_refresh_cookie(response)  # dead token: don't keep sending it
            return response
        return token_response(message="Token refreshed.", tokens=tokens)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=AUTH_TAG,
        summary="Log out of this device",
        description=(
            "Ends the current session immediately: its access AND refresh tokens "
            "stop working at once. Other devices stay logged in."
        ),
        request=LogoutSerializer,
        responses={200: OpenApiResponse(description="Logged out.")},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        logout(
            request.user,
            session_id=_current_session_id(request),
            raw_refresh=serializer.validated_data.get("refresh"),
        )
        response = ApiResponse.success(message="Logged out successfully.")
        clear_refresh_cookie(response)
        return response


class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=SESSIONS_TAG,
        summary="Log out of all devices",
        description="Ends every session of this account, including the current one.",
        request=None,
        responses={200: OpenApiResponse(description="All sessions ended.")},
    )
    def post(self, request):
        count = logout_everywhere(request.user)
        revoke_trusted_devices(request.user, TrustedDevice.RevokeReason.LOGOUT_ALL)
        response = ApiResponse.success(
            message="Logged out of all devices.", data={"sessions_ended": count}
        )
        clear_refresh_cookie(response)
        clear_device_cookie(response)
        return response


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=SESSIONS_TAG,
        summary="List my active sessions (devices)",
        responses={200: UserSessionSerializer(many=True)},
    )
    def get(self, request):
        sessions = UserSession.objects.active().filter(user=request.user)
        serializer = UserSessionSerializer(
            sessions,
            many=True,
            context={"current_session_id": _current_session_id(request)},
        )
        return ApiResponse.success(data=serializer.data)


class SessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=SESSIONS_TAG,
        summary="End one of my sessions (log out another device)",
        request=None,
        responses={
            200: OpenApiResponse(description="Session ended."),
            404: OpenApiResponse(
                description="NOT_FOUND (not your session, or already ended)"
            ),
        },
    )
    def delete(self, request, pk: int):
        # Scoped to the requester: someone else's session id is simply "not found".
        session = get_object_or_404(
            UserSession.objects.active(), pk=pk, user=request.user
        )
        revoke_session(session, UserSession.RevokeReason.REVOKED_BY_USER)
        return ApiResponse.success(message="Session ended.")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=AUTH_TAG, summary="Current user", responses={200: UserSerializer}
    )
    def get(self, request):
        return ApiResponse.success(data=UserSerializer(request.user).data)

    @extend_schema(
        tags=AUTH_TAG,
        summary="Edit my name",
        request=NameUpdateSerializer,
        responses={200: UserSerializer},
    )
    def patch(self, request):
        serializer = NameUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = update_user_details(
            actor=request.user,
            target=request.user,
            first_name=serializer.validated_data.get("first_name"),
            last_name=serializer.validated_data.get("last_name"),
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Updated.", data=UserSerializer(user).data)
