from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.identifiers import normalize_identifier
from apps.accounts.models import User


class _IdentifierSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=OTPChannel.choices)
    identifier = serializers.CharField(
        max_length=254,
        help_text="Email address (channel=EMAIL) or phone number (channel=PHONE).",
    )
    purpose = serializers.ChoiceField(choices=OTPPurpose.choices)

    def validate(self, attrs):
        try:
            attrs["identifier"] = normalize_identifier(
                attrs["channel"], attrs["identifier"]
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"identifier": exc.messages}) from None
        return attrs


class OTPRequestSerializer(_IdentifierSerializer):
    """Unknown fields (e.g. a smuggled "role") are ignored, never applied."""


class OTPVerifySerializer(_IdentifierSerializer):
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "The OTP must be 6 digits."},
    )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "role",
            "email_verified_at",
            "phone_verified_at",
            "created_at",
        ]
        read_only_fields = fields


class AuthTokensSerializer(serializers.Serializer):
    """Response shape of a successful OTP verification (documentation only)."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class SafeTokenRefreshSerializer(TokenRefreshSerializer):
    """
    SimpleJWT looks the user up with `User.objects.get(...)`. Our default
    manager hides soft-deleted users, so for a deleted account that raises
    DoesNotExist, which would surface as a 500. Treat it as what it is:
    no active account.
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise AuthenticationFailed(
                "No active account found for this token.", code="no_active_account"
            ) from None
