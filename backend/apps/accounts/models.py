"""
The User model: *who can authenticate*.

Deliberately minimal. Student details live in StudentProfile, money in fee
models, etc. (see the spec's "separate concepts" principle). A user signs in
with an email OR a phone number (OTP-based), so both are optional
individually but at least one must exist.
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.managers import UserManager
from apps.common.models import AbstractTimeStampedModel, GlobalTimeStampedModel

# E.164 international format, e.g. +919876543210
phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Phone number must be in international format, e.g. +919876543210.",
)


class User(AbstractTimeStampedModel, AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        STUDENT = "STUDENT", "Student"

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=16, unique=True, null=True, blank=True, validators=[phone_validator]
    )
    # Role is never settable through public registration; ADMIN accounts are
    # provisioned only via the trusted `createsuperuser` path (or a future
    # admin-only endpoint).
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.STUDENT, db_index=True
    )

    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False, help_text="Can log in to the Django admin site."
    )

    objects = UserManager()  # hides soft-deleted users
    all_objects = models.Manager()  # includes soft-deleted users (audits, admin)

    # Used by the Django admin login and createsuperuser. Regular users
    # authenticate through OTP, not passwords.
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(phone__isnull=False),
                name="users_email_or_phone_required",
            ),
        ]

    def __str__(self) -> str:
        return self.email or self.phone or str(self.id)

    def save(self, *args, **kwargs):
        # Normalise so "A@X.com" and "a@x.com" can never become two accounts,
        # and store empty strings as NULL so the unique constraints work.
        self.email = self.email.strip().lower() if self.email else None
        self.phone = self.phone.strip() if self.phone else None
        super().save(*args, **kwargs)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT


class OTPChallenge(GlobalTimeStampedModel):
    """
    One OTP sent to one email/phone for one purpose.

    - The code itself is never stored, only its hash (like a password), so a
      database leak does not reveal usable codes.
    - At most ONE active challenge per (channel, identifier, purpose), enforced
      by the database: requesting a new OTP invalidates the previous one.
    - Rows are kept after use (consumed/invalidated) as an audit trail.
    """

    channel = models.CharField(max_length=8, choices=OTPChannel.choices)
    identifier = models.CharField(
        max_length=254, help_text="Normalised email or E.164 phone number."
    )
    purpose = models.CharField(max_length=16, choices=OTPPurpose.choices)
    code_hash = models.CharField(max_length=128)

    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField()

    consumed_at = models.DateTimeField(
        null=True, blank=True, help_text="Set when verified successfully."
    )
    invalidated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when superseded, expired, locked out, or undeliverable.",
    )
    requested_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "otp_challenges"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["channel", "identifier", "purpose", "-created_at"],
                name="otp_challenges_lookup_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "identifier", "purpose"],
                condition=Q(consumed_at__isnull=True, invalidated_at__isnull=True),
                name="otp_challenges_one_active_per_identity",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.purpose} OTP via {self.channel} (#{self.pk})"


class UserSessionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())


class UserSession(GlobalTimeStampedModel):
    """
    One login on one device (pattern from Labe1 Label_Auth's UserSession).

    Every JWT carries this session's `session_id` as its `sid` claim. The
    claim survives refresh-token rotation, so one row identifies one login
    for its whole lifetime. Revoking the row immediately kills every access
    and refresh token of that login, even ones that haven't expired yet.
    """

    class RevokeReason(models.TextChoices):
        LOGOUT = "LOGOUT", "Logged out"
        LOGOUT_ALL = "LOGOUT_ALL", "Logged out of all devices"
        REVOKED_BY_USER = "REVOKED_BY_USER", "Revoked from another device"
        REFRESH_REUSE = "REFRESH_REUSE", "Refresh token reuse detected"
        LIFETIME_EXCEEDED = "LIFETIME_EXCEEDED", "Maximum session lifetime reached"
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED", "Account deactivated"
        ROLE_CHANGED = "ROLE_CHANGED", "Role changed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="The `sid` claim carried by this login's tokens.",
    )
    refresh_token_jti = models.CharField(
        max_length=64,
        db_index=True,
        help_text="jti of this session's CURRENT refresh token (changes on every rotation).",
    )
    last_active_at = models.DateTimeField(
        default=timezone.now, help_text="Last login or token refresh."
    )
    expires_at = models.DateTimeField(
        help_text="When the current refresh token expires (slides on each refresh)."
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(
        max_length=32, choices=RevokeReason.choices, blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    objects = UserSessionQuerySet.as_manager()

    class Meta:
        db_table = "user_sessions"
        ordering = ["-last_active_at"]
        indexes = [
            models.Index(
                fields=["user", "revoked_at"], name="user_sessions_user_active_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"Session #{self.pk} of user {self.user_id}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()
