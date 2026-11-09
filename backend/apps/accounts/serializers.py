from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.choices import PUBLIC_OTP_PURPOSES, OTPChannel
from apps.accounts.identifiers import normalize_identifier
from apps.accounts.models import User, UserSession
from apps.accounts.services.sms import EMAIL_REQUIRED_MESSAGE, sms_enabled


def _otp_code_field():
    return serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "The OTP must be 6 digits."},
    )


class _ChannelIdentifierSerializer(serializers.Serializer):
    """channel + identifier, with the identifier normalised for its channel."""

    channel = serializers.ChoiceField(choices=OTPChannel.choices)
    identifier = serializers.CharField(
        max_length=254,
        help_text="Email address (channel=EMAIL) or phone number (channel=PHONE).",
    )

    def validate(self, attrs):
        if attrs.get("identifier") is None:
            return attrs
        try:
            attrs["identifier"] = normalize_identifier(
                attrs["channel"], attrs["identifier"]
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"identifier": exc.messages}) from None
        return attrs


class _IdentifierSerializer(_ChannelIdentifierSerializer):
    purpose = serializers.ChoiceField(
        choices=PUBLIC_OTP_PURPOSES,
        default="LOGIN",
        help_text="Only LOGIN: accounts are created by the institute (invite-only).",
    )


class OTPRequestSerializer(_IdentifierSerializer):
    """Unknown fields (e.g. a smuggled "role") are ignored, never applied."""


class OTPVerifySerializer(_IdentifierSerializer):
    code = _otp_code_field()


class ContactChangeSerializer(_ChannelIdentifierSerializer):
    """The NEW email/phone to add or switch to."""


class ContactVerifySerializer(_ChannelIdentifierSerializer):
    code = _otp_code_field()


class AdminContactSerializer(_ChannelIdentifierSerializer):
    identifier = serializers.CharField(
        max_length=254,
        allow_null=True,
        help_text="New email/phone, or null to remove it.",
    )


class UserSerializer(serializers.ModelSerializer):
    google_linked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "email_verified_at",
            "phone_verified_at",
            "google_linked",
            "created_at",
        ]
        read_only_fields = fields

    def get_google_linked(self, obj) -> bool:
        return bool(obj.google_id)


class GoogleSignInSerializer(serializers.Serializer):
    id_token = serializers.CharField(
        help_text="The Google ID token (credential) the frontend received from Google."
    )


class GoogleVerifySerializer(GoogleSignInSerializer):
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "The OTP must be 6 digits."},
    )


class GoogleSignInResponseSerializer(serializers.Serializer):
    """Documentation only."""

    status = serializers.ChoiceField(choices=["AUTHENTICATED", "OTP_REQUIRED"])
    access = serializers.CharField(required=False, help_text="Only when AUTHENTICATED.")
    refresh = serializers.CharField(
        required=False, help_text="Only when AUTHENTICATED."
    )
    user = UserSerializer(required=False, help_text="Only when AUTHENTICATED.")
    email = serializers.CharField(
        required=False, help_text="Masked email the code was sent to (OTP_REQUIRED)."
    )
    expires_in_seconds = serializers.IntegerField(required=False)
    resend_after_seconds = serializers.IntegerField(required=False)


class AdminUserSerializer(serializers.ModelSerializer):
    """What administrators see about an account. Read-only: changes go through actions."""

    invite_accepted = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
            "is_superuser",
            "email_verified_at",
            "phone_verified_at",
            "last_login",
            "invited_by",
            "activated_at",
            "invite_accepted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_invite_accepted(self, obj) -> bool:
        return obj.activated_at is not None


class _NameFieldsMixin(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, trim_whitespace=True)
    last_name = serializers.CharField(max_length=150, trim_whitespace=True)


class InviteUserSerializer(_NameFieldsMixin):
    """Create a login. Give an email, a phone, or both; the invite goes to each."""

    role = serializers.ChoiceField(choices=User.Role.choices)
    email = serializers.CharField(max_length=254, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate(self, attrs):
        errors = {}
        for channel, field in (
            (OTPChannel.EMAIL, "email"),
            (OTPChannel.PHONE, "phone"),
        ):
            raw = attrs.get(field) or None
            if raw is None:
                attrs[field] = None
                continue
            try:
                attrs[field] = normalize_identifier(channel, raw)
            except DjangoValidationError as exc:
                errors[field] = exc.messages
        if not errors and not attrs["email"] and not attrs["phone"]:
            errors["non_field_errors"] = ["Give an email, a phone number, or both."]
        elif not errors and not attrs["email"] and not sms_enabled():
            errors["email"] = [EMAIL_REQUIRED_MESSAGE]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class NameUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        max_length=150, required=False, trim_whitespace=True
    )
    last_name = serializers.CharField(
        max_length=150, required=False, trim_whitespace=True
    )


class InviteResultSerializer(serializers.Serializer):
    """Documentation only."""

    user = AdminUserSerializer()
    invite_sent = serializers.DictField(
        child=serializers.BooleanField(),
        help_text='Per channel attempted, e.g. {"email": true, "phone": false}.',
    )


class RoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class AuthTokensSerializer(serializers.Serializer):
    """Response shape of a successful OTP verification (documentation only)."""

    access = serializers.CharField()
    refresh = serializers.CharField(
        required=False,
        help_text=(
            "Only when REFRESH_TOKEN_IN_BODY is on (development). "
            "Browsers receive it as an HttpOnly cookie."
        ),
    )
    user = UserSerializer()


class TokenPairSerializer(serializers.Serializer):
    """Response shape of a token refresh (documentation only)."""

    access = serializers.CharField()
    refresh = serializers.CharField(
        required=False,
        help_text=(
            "Only when REFRESH_TOKEN_IN_BODY is on (development). "
            "Browsers receive it as an HttpOnly cookie."
        ),
    )


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=(
            "Omit in browsers (the HttpOnly cookie is used). "
            "The current refresh token. Rotation is on: the response carries a NEW "
            "refresh token; store it and discard this one."
        ),
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
