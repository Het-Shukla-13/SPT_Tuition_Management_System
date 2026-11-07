from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.identifiers import normalize_identifier
from apps.accounts.models import User, UserSession


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


class AdminUserSerializer(serializers.ModelSerializer):
    """What administrators see about an account. Read-only: changes go through actions."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "role",
            "is_active",
            "is_superuser",
            "email_verified_at",
            "phone_verified_at",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class AuthTokensSerializer(serializers.Serializer):
    """Response shape of a successful OTP verification (documentation only)."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class TokenPairSerializer(serializers.Serializer):
    """Response shape of a token refresh (documentation only)."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        help_text=(
            "The current refresh token. Rotation is on: the response carries a NEW "
            "refresh token; store it and discard this one."
        )
    )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        required=False,
        help_text="Optional. If sent, it must belong to the logged-in user.",
    )


class UserSessionSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField(
        help_text="True for the session making this request."
    )

    class Meta:
        model = UserSession
        fields = [
            "id",
            "created_at",
            "last_active_at",
            "expires_at",
            "ip_address",
            "user_agent",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, obj) -> bool:
        return obj.session_id == self.context.get("current_session_id")
