"""
Password login, new-device codes, first/forgot password, change password and
trusted devices (Phase 1.5). Thin views: the decisions live in
services/passwords.py and services/devices.py.
"""

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import TrustedDevice
from apps.accounts.serializers import (
    AuthTokensSerializer,
    LoginResultSerializer,
    LoginSerializer,
    LoginTicketSerializer,
    LoginVerifySerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TrustedDeviceSerializer,
    UserSerializer,
)
from apps.accounts.services.auth_cookies import set_device_cookie, token_response
from apps.accounts.services.devices import (
    device_token_from,
    hash_device_token,
    trust_device,
)
from apps.accounts.services.passwords import (
    change_password,
    login_with_password,
    request_password_code,
    resend_new_device_code,
    reset_password,
    verify_new_device,
)
from apps.accounts.services.sessions import SID_CLAIM
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.common.request_utils import client_ip, user_agent
from apps.common.responses import ApiResponse
from apps.common.throttling import ResilientScopedRateThrottle

PASSWORD_TAG = ["Auth: password"]
DEVICES_TAG = ["Auth: trusted devices"]


def log_in(request, user, *, message: str, trust: bool, extra: dict | None = None):
    """Start a session for `user`; when `trust`, remember this browser too."""
    tokens = issue_tokens(user, ip=client_ip(request), user_agent=user_agent(request))
    response = token_response(
        message=message,
        tokens=tokens,
        extra={
            "status": "AUTHENTICATED",
            "user": UserSerializer(user).data,
            **(extra or {}),
        },
    )
    if trust:
        token = trust_device(
            user,
            token=device_token_from(request),
            ip=client_ip(request),
            user_agent=user_agent(request),
        )
        set_device_cookie(response, token)
    return response


def _code_sent(*, email: str | None, extra: dict | None = None) -> dict:
    return {
        "status": "OTP_REQUIRED",
        "email": email,
        "expires_in_seconds": settings.OTP_TTL_SECONDS,
        "resend_after_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
        **(extra or {}),
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        tags=PASSWORD_TAG,
        summary="Log in with email + password",
        description=(
            "- Trusted device (this browser passed a code within the last 90 days): "
            "`status: AUTHENTICATED`, tokens as for any login.\n"
            "- New device: `status: OTP_REQUIRED`, a code is emailed; send it with the "
            "returned `login_ticket` to `login/verify/`.\n\n"
            "Any wrong email/password (or an account without a password yet) gives the "
            "same `INVALID_CREDENTIALS`. 5 wrong passwords lock the email for 15 minutes "
            "(`LOGIN_LOCKED`)."
        ),
        request=LoginSerializer,
        responses={
            200: LoginResultSerializer,
            400: OpenApiResponse(description="VALIDATION_ERROR / INVALID_CREDENTIALS"),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            429: OpenApiResponse(
                description="LOGIN_LOCKED / OTP_REQUEST_LIMIT_REACHED / THROTTLED"
            ),
            503: OpenApiResponse(description="OTP_DELIVERY_FAILED"),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = login_with_password(
            **serializer.validated_data,
            device_token=device_token_from(request),
            ip=client_ip(request),
        )
        if result.user is not None:
            return log_in(request, result.user, message="Logged in.", trust=False)
        return ApiResponse.success(
            message="This device is new: enter the code we emailed you.",
            data=_code_sent(
                email=result.masked_email, extra={"login_ticket": result.ticket}
            ),
        )


class LoginVerifyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(
        tags=PASSWORD_TAG,
        summary="Finish a new-device login with the emailed code",
        description="Logs in and trusts this device for 90 days.",
        request=LoginVerifySerializer,
        responses={
            200: AuthTokensSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR / OTP_INVALID / OTP_EXPIRED / LOGIN_TICKET_INVALID"
            ),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            429: OpenApiResponse(description="OTP_ATTEMPTS_EXCEEDED / THROTTLED"),
        },
    )
    def post(self, request):
        serializer = LoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_new_device(
            ticket=serializer.validated_data["login_ticket"],
            code=serializer.validated_data["code"],
        )
        return log_in(
            request, user, message="Verified. This device is now trusted.", trust=True
        )


class LoginResendView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=PASSWORD_TAG,
        summary="Email a new code for a pending new-device login",
        request=LoginTicketSerializer,
        responses={
            200: OpenApiResponse(description="Code sent."),
            400: OpenApiResponse(description="LOGIN_TICKET_INVALID"),
            429: OpenApiResponse(
                description="OTP_COOLDOWN / OTP_REQUEST_LIMIT_REACHED"
            ),
        },
    )
    def post(self, request):
        serializer = LoginTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = resend_new_device_code(
            ticket=serializer.validated_data["login_ticket"], ip=client_ip(request)
        )
        return ApiResponse.success(
            message="A new code has been sent.", data=_code_sent(email=email)
        )


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_request"

    @extend_schema(
        tags=PASSWORD_TAG,
        summary="Set or reset password: email a code",
        description=(
            "For a first password (invited users have none) and for a forgotten one. "
            "The answer is the same whether or not the email has an account."
        ),
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description="Request accepted."),
            429: OpenApiResponse(
                description="OTP_COOLDOWN / OTP_REQUEST_LIMIT_REACHED / THROTTLED"
            ),
            503: OpenApiResponse(description="OTP_DELIVERY_FAILED"),
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_code(
            email=serializer.validated_data["email"], ip=client_ip(request)
        )
        return ApiResponse.success(
            message="If this email has an account, we've sent a code to it.",
            data=_code_sent(email=None) | {"status": "CODE_SENT"},
        )


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(
        tags=PASSWORD_TAG,
        summary="Set or reset password: code + new password",
        description=(
            "Sets the password and logs in, trusting this device. Every OTHER session "
            "and trusted device of the account ends (the old password may be known)."
        ),
        request=PasswordResetConfirmSerializer,
        responses={
            200: AuthTokensSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR (weak password: errors.new_password) / OTP_INVALID / OTP_EXPIRED"
            ),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
            429: OpenApiResponse(description="OTP_ATTEMPTS_EXCEEDED / THROTTLED"),
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = reset_password(**serializer.validated_data, ip=client_ip(request))
        return log_in(
            request, user, message="Password saved. You're logged in.", trust=True
        )


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        tags=PASSWORD_TAG,
        summary="Change my password",
        description=(
            "Your other devices are logged out and will need a code next time; this "
            "device stays logged in and trusted."
        ),
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description="Password changed."),
            400: OpenApiResponse(description="VALIDATION_ERROR / WRONG_PASSWORD"),
            429: OpenApiResponse(description="LOGIN_LOCKED / THROTTLED"),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_password(
            user=request.user,
            **serializer.validated_data,
            session_id=request.auth.get(SID_CLAIM)
            if request.auth is not None
            else None,
            device_token=device_token_from(request),
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Password changed. Your other devices were logged out."
        )


class TrustedDeviceListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=DEVICES_TAG,
        summary="My trusted devices",
        responses={200: TrustedDeviceSerializer(many=True)},
    )
    def get(self, request):
        token = device_token_from(request)
        devices = TrustedDevice.objects.active().filter(user=request.user)
        context = {"current_hash": hash_device_token(token) if token else None}
        return ApiResponse.success(
            data=TrustedDeviceSerializer(devices, many=True, context=context).data
        )


class TrustedDeviceRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=DEVICES_TAG,
        summary="Stop trusting one of my devices",
        description="Its next login needs an emailed code again. Doesn't log it out.",
        request=None,
        responses={
            200: OpenApiResponse(description="Removed."),
            404: OpenApiResponse(description="NOT_FOUND"),
        },
    )
    def delete(self, request, pk: int):
        device = get_object_or_404(
            TrustedDevice.objects.active(), pk=pk, user=request.user
        )
        device.revoked_at = timezone.now()
        device.revoked_reason = TrustedDevice.RevokeReason.REMOVED
        device.save(update_fields=["revoked_at", "revoked_reason", "updated_at"])
        record(
            AuditLog.Action.TRUSTED_DEVICE_REMOVED,
            actor=request.user,
            target=request.user,
            changes={"device_id": device.pk},
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Device removed.")
