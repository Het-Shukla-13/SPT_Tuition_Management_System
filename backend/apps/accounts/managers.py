from django.contrib.auth.base_user import BaseUserManager
from django.core.exceptions import ValidationError


class UserManager(BaseUserManager):
    """Soft-delete-aware user manager (like Labe1's SoftDeleteUserManager)."""

    use_in_migrations = True

    def get_queryset(self):
        # Soft-deleted users can't be found, so they can't log in either.
        return super().get_queryset().filter(is_deleted=False)

    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        """
        Create a regular (STUDENT by default) user.

        OTP users have no password: `set_unusable_password()` makes password
        login impossible for them instead of storing an empty/guessable one.
        """
        if not email and not phone:
            raise ValueError("A user must have an email or a phone number.")

        email = self.normalize_email(email).lower() if email else None
        phone = phone.strip() if phone else None
        self._ensure_identity_unused(email=email, phone=phone)

        user = self.model(email=email, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def _ensure_identity_unused(self, *, email, phone):
        """
        Reject an email/phone already used by ANY user, including soft-deleted
        ones. Django's built-in unique validation goes through this manager,
        which hides deleted users, so it would miss them and fail later with a
        raw database IntegrityError instead of a clean validation error.
        """
        all_users = self.model.all_objects.using(self._db)
        errors = {}
        if email and all_users.filter(email=email).exists():
            errors["email"] = ["A user with this email already exists."]
        if phone and all_users.filter(phone=phone).exists():
            errors["phone"] = ["A user with this phone number already exists."]
        if errors:
            raise ValidationError(errors)

    def create_superuser(self, email, password, **extra_fields):
        """Trusted, command-line-only path for provisioning an administrator."""
        from apps.accounts.models import User

        if not email:
            raise ValueError("A superuser must have an email address.")
        if not password:
            raise ValueError("A superuser must have a password.")

        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields["role"] != User.Role.ADMIN:
            raise ValueError("A superuser must have role=ADMIN.")
        if (
            extra_fields["is_staff"] is not True
            or extra_fields["is_superuser"] is not True
        ):
            raise ValueError(
                "A superuser must have is_staff=True and is_superuser=True."
            )

        return self.create_user(email=email, password=password, **extra_fields)
