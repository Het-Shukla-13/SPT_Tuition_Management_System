"""
The User model: *who can authenticate*.

Deliberately minimal. Student details live in StudentProfile, money in fee
models, etc. (see the spec's "separate concepts" principle). A user signs in
with email + password (plus an emailed code on new devices), Google, or a
phone OTP, so email and phone are optional individually but at least one
must exist.
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
        TEACHER = "TEACHER", "Teacher"
        # A parent or student who logs in to view the student(s) linked to
        # this login (see students.StudentAccess).
        PORTAL = "PORTAL", "Portal user"

    # Names are filled in by whoever creates the login (invite), like Labe1.
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=16, unique=True, null=True, blank=True, validators=[phone_validator]
    )
    # Invite-only platform: logins are created by the owner/admins, never by
    # the public. ADMIN can only be granted by the owner.
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.PORTAL, db_index=True
    )
    invited_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Who created this login.",
    )
    activated_at = models.DateTimeField(
        null=True, blank=True, help_text="First successful login (invite accepted)."
    )

    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    # Google's stable account id (the `sub` claim), as in Labe1. One Google
    # account can be linked to at most one user. The raw Google token is never
    # stored: it isn't needed after verification.
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    google_linked_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False, help_text="Can log in to the Django admin site."
    )

    objects = UserManager()  # hides soft-deleted users
    all_objects = models.Manager()  # includes soft-deleted users (audits, admin)

    # Email + password login (Phase 1.5) and the Django admin both use
    # AbstractBaseUser's hashed `password`. Invited users have no usable
    # password until they set one through the emailed-code flow.
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
        return self.full_name or self.email or self.phone or str(self.id)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        # Normalise so "A@X.com" and "a@x.com" can never become two accounts,
        # and store empty strings as NULL so the unique constraints work.
        self.email = self.email.strip().lower() if self.email else None
        self.phone = self.phone.strip() if self.phone else None
        self.google_id = self.google_id or None
        super().save(*args, **kwargs)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_teacher(self) -> bool:
        return self.role == self.Role.TEACHER

    @property
    def is_portal_user(self) -> bool:
        return self.role == self.Role.PORTAL


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
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Facts the code is bound to, e.g. {"google_sub": "..."} for GOOGLE_LINK.',
    )

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
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed or reset"

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
    # The student this device last picked in the portal (like Labe1's
    # per-session active group). Convenience only: every request re-checks
    # access, so this is never a permission.
    selected_student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

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


class TrustedDeviceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())


class TrustedDevice(GlobalTimeStampedModel):
    """
    A browser that has passed the emailed-code check for this user (Phase 1.5).

    On a trusted device a correct password (or Google) logs straight in; on
    any other device an emailed code is needed first. The browser keeps a
    random token in an HttpOnly cookie; only its SHA-256 hash is stored here,
    so a database leak doesn't let anyone pose as a trusted device.

    One browser (one cookie) can be trusted by several people, e.g. a shared
    family laptop: one row per (user, token).
    """

    class RevokeReason(models.TextChoices):
        REMOVED = "REMOVED", "Removed by the user"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"
        LOGOUT_ALL = "LOGOUT_ALL", "Logged out of all devices"
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED", "Account deactivated"
        ROLE_CHANGED = "ROLE_CHANGED", "Role changed"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="trusted_devices"
    )
    token_hash = models.CharField(
        max_length=64, help_text="SHA-256 of the cookie token."
    )
    label = models.CharField(
        max_length=512, blank=True, help_text="Browser / device description."
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(
        max_length=32, choices=RevokeReason.choices, blank=True
    )

    objects = TrustedDeviceQuerySet.as_manager()

    class Meta:
        db_table = "trusted_devices"
        ordering = ["-last_used_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "token_hash"], name="trusted_devices_one_row_per_user"
            ),
        ]

    def __str__(self) -> str:
        return f"Trusted device #{self.pk} of user {self.user_id}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()
