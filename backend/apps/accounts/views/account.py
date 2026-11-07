"""Account settings: /api/v1/auth/me/contact/... (logic in services/contact.py)."""

from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.choices import OTPChannel
from apps.accounts.identifiers import mask_identifier
from apps.accounts.serializers import (
    ContactChangeSerializer,
    ContactVerifySerializer,
    UserSerializer,
)
from apps.accounts.services.contact import (
    complete_contact_change,
    remove_contact,
    start_contact_change,
)
from apps.common.request_utils import client_ip
from apps.common.responses import ApiResponse
from apps.common.throttling import ResilientScopedRateThrottle

ACCOUNT_TAG = ["Auth: account settings"]
_CHANNEL_BY_SLUG = {"email": OTPChannel.EMAIL, "phone": OTPChannel.PHONE}


class ContactChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "contact_change"

    @extend_schema(
        tags=ACCOUNT_TAG,
        summary="Add or change my email/phone (step 1: send a code to the new one)",
        request=ContactChangeSerializer,
        responses={
            200: OpenApiResponse(description="Code sent to the new email/phone."),
            400: OpenApiResponse(description="VALIDATION_ERROR / CONTACT_UNCHANGED"),
            409: OpenApiResponse(description="CONTACT_IN_USE"),
            429: OpenApiResponse(
                description="OTP_COOLDOWN / OTP_REQUEST_LIMIT_REACHED / THROTTLED"
            ),
            503: OpenApiResponse(description="OTP_DELIVERY_FAILED"),
        },
    )
    def post(self, request):
        serializer = ContactChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        start_contact_change(
            user=request.user, **serializer.validated_data, ip=client_ip(request)
        )
        data = serializer.validated_data
        return ApiResponse.success(
            message="A verification code has been sent to the new email/phone.",
            data={
                "sent_to": mask_identifier(data["channel"], data["identifier"]),
                "expires_in_seconds": settings.OTP_TTL_SECONDS,
                "resend_after_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
            },
        )


class ContactVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "otp_verify"

    @extend_schema(
        tags=ACCOUNT_TAG,
        summary="Add or change my email/phone (step 2: confirm the code)",
        description="Saves the new email/phone as verified. The old one is notified.",
        request=ContactVerifySerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="OTP_INVALID / OTP_EXPIRED"),
            409: OpenApiResponse(description="CONTACT_IN_USE"),
            429: OpenApiResponse(description="OTP_ATTEMPTS_EXCEEDED"),
        },
    )
    def post(self, request):
        serializer = ContactVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = complete_contact_change(
            user=request.user, **serializer.validated_data, ip=client_ip(request)
        )
        return ApiResponse.success(
            message="Contact details updated.", data=UserSerializer(user).data
        )


class ContactRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=ACCOUNT_TAG,
        summary="Remove my email or phone",
        description="Only allowed if the other one remains, so you can still log in.",
        request=None,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="CONTACT_NOT_SET / LAST_CONTACT_METHOD"),
        },
    )
    def delete(self, request, kind: str):
        channel = _CHANNEL_BY_SLUG.get(kind)
        if channel is None:
            raise Http404
        user = remove_contact(user=request.user, channel=channel, ip=client_ip(request))
        return ApiResponse.success(message="Removed.", data=UserSerializer(user).data)
