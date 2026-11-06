"""
Authentication endpoints. Views stay thin: validate input, call a service,
shape the response. All decisions live in apps/accounts/services/.
"""

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.serializers import (
    AuthTokensSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    SafeTokenRefreshSerializer,
    UserSerializer,
)
from apps.accounts.services.otp import request_otp, verify_otp
from apps.accounts.services.tokens import issue_tokens, revoke_refresh_token
from apps.common.responses import ApiResponse
from apps.common.throttling import ResilientScopedRateThrottle

AUTH_TAG = ["Auth"]


def _client_ip(request) -> str | None:
    # REMOTE_ADDR only. X-Forwarded-For is trivially spoofable and will be
    # trusted only once we know the production proxy setup (deployment phase).
    return request.META.get("REMOTE_ADDR")


class OTPRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=AUTH_TAG,
        summary="Request an OTP (register or login)",
        description=(
            "Sends a one-time code to the email/phone for the given purpose. "
            "The response is identical whether or not an account exists, so this "
            "endpoint cannot be used to discover registered users.\n\n"
            "- `REGISTER` for an existing account: no code is sent; the owner is told "
            "they already have an account.\n"
            "- `LOGIN` for an unknown/disabled account: nothing is sent.\n\n"
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
        request_otp(**serializer.validated_data, ip=_client_ip(request))
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
            "`REGISTER` creates a STUDENT account and logs it in. "
            "`LOGIN` logs into the existing account. Returns access + refresh tokens."
        ),
        request=OTPVerifySerializer,
        responses={
            200: AuthTokensSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR / OTP_INVALID / OTP_EXPIRED"
            ),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            409: OpenApiResponse(description="ACCOUNT_ALREADY_EXISTS"),
            429: OpenApiResponse(description="OTP_ATTEMPTS_EXCEEDED / THROTTLED"),
        },
    )
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_otp(**serializer.validated_data)
        return ApiResponse.success(
            message="Verified successfully.",
            data={**issue_tokens(user), "user": UserSerializer(user).data},
        )


class TokenRefreshEnvelopeView(TokenRefreshView):
    """
    Exchange a refresh token for a new access token. Refresh tokens rotate:
    the response carries a NEW refresh token and the old one is blacklisted.
    """

    serializer_class = SafeTokenRefreshSerializer

    @extend_schema(tags=AUTH_TAG, summary="Refresh the access token")
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return ApiResponse.success(message="Token refreshed.", data=response.data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=AUTH_TAG,
        summary="Log out (revoke the refresh token)",
        description=(
            "Blacklists the given refresh token so it can't mint new access tokens. "
            "The current access token stays valid until it expires (max 15 min); "
            "the frontend must discard it."
        ),
        request=LogoutSerializer,
        responses={200: OpenApiResponse(description="Logged out.")},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoke_refresh_token(request.user, serializer.validated_data["refresh"])
        return ApiResponse.success(message="Logged out successfully.")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=AUTH_TAG, summary="Current user", responses={200: UserSerializer}
    )
    def get(self, request):
        return ApiResponse.success(data=UserSerializer(request.user).data)
