"""Google Sign-In endpoints: /api/v1/auth/google/... (logic in services/google.py)."""

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.identifiers import mask_email
from apps.accounts.serializers import (
    AuthTokensSerializer,
    GoogleSignInResponseSerializer,
    GoogleSignInSerializer,
    GoogleVerifySerializer,
    UserSerializer,
)
from apps.accounts.services.auth_cookies import token_response
from apps.accounts.services.google import (
    complete_google_sign_in,
    start_google_sign_in,
    unlink_google,
)
from apps.accounts.services.tokens import issue_tokens
from apps.common.request_utils import client_ip, user_agent
from apps.common.responses import ApiResponse
from apps.common.throttling import ResilientScopedRateThrottle

GOOGLE_TAG = ["Auth: Google"]


def _login_response(request, user, message: str):
    tokens = issue_tokens(user, ip=client_ip(request), user_agent=user_agent(request))
    return token_response(
        message=message,
        tokens=tokens,
        extra={"status": "AUTHENTICATED", "user": UserSerializer(user).data},
    )


class GoogleSignInView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=GOOGLE_TAG,
        summary="Continue with Google (step 1)",
        description=(
            "Send the Google ID token the frontend got from Google.\n\n"
            "- `status: AUTHENTICATED`: this Google account is already linked. "
            "Tokens are returned; you're logged in.\n"
            "- `status: OTP_REQUIRED`: first time with this Google account. A 6-digit "
            "code was emailed to the Google account's address; call "
            "`google/verify/` with the same `id_token` and the code."
        ),
        request=GoogleSignInSerializer,
        responses={
            200: GoogleSignInResponseSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR / GOOGLE_EMAIL_NOT_VERIFIED"
            ),
            401: OpenApiResponse(description="GOOGLE_TOKEN_INVALID"),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            429: OpenApiResponse(
                description="OTP_COOLDOWN / OTP_REQUEST_LIMIT_REACHED / THROTTLED"
            ),
            503: OpenApiResponse(
                description="GOOGLE_UNAVAILABLE / OTP_DELIVERY_FAILED"
            ),
        },
    )
    def post(self, request):
        serializer = GoogleSignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = start_google_sign_in(
            raw_token=serializer.validated_data["id_token"], ip=client_ip(request)
        )
        if result.user is not None:
            return _login_response(request, result.user, "Signed in with Google.")
        return ApiResponse.success(
            message="Enter the verification code sent to your email to finish signing in.",
            data={
                "status": "OTP_REQUIRED",
                "email": mask_email(result.email),
                "expires_in_seconds": settings.OTP_TTL_SECONDS,
                "resend_after_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
            },
        )


class GoogleVerifyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(
        tags=GOOGLE_TAG,
        summary="Continue with Google (step 2: verify the emailed code)",
        description=(
            "Links the Google account to the invited account that owns the email and "
            "logs in. Later Google sign-ins are one-click. Google never creates accounts."
        ),
        request=GoogleVerifySerializer,
        responses={
            200: AuthTokensSerializer,
            400: OpenApiResponse(
                description="OTP_INVALID / OTP_EXPIRED / GOOGLE_EMAIL_NOT_VERIFIED"
            ),
            401: OpenApiResponse(description="GOOGLE_TOKEN_INVALID"),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            409: OpenApiResponse(description="GOOGLE_ACCOUNT_CONFLICT"),
            429: OpenApiResponse(description="OTP_ATTEMPTS_EXCEEDED / THROTTLED"),
        },
    )
    def post(self, request):
        serializer = GoogleVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = complete_google_sign_in(
            raw_token=serializer.validated_data["id_token"],
            code=serializer.validated_data["code"],
            ip=client_ip(request),
        )
        return _login_response(request, user, "Google account linked. Signed in.")


class GoogleUnlinkView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=GOOGLE_TAG,
        summary="Unlink my Google account",
        description=(
            "Google sign-in stops working for this account (email OTP still works). "
            "Signing in with Google again later will require an email code."
        ),
        request=None,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="GOOGLE_NOT_LINKED"),
        },
    )
    def post(self, request):
        user = unlink_google(user=request.user, ip=client_ip(request))
        return ApiResponse.success(
            message="Google account unlinked.", data=UserSerializer(user).data
        )
