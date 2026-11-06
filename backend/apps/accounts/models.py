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

from apps.accounts.managers import UserManager
from apps.common.models import AbstractTimeStampedModel

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
