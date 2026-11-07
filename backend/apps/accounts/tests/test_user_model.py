import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email_defaults_to_student_without_password(self):
        user = User.objects.create_user(email="Student@Example.com")

        assert user.email == "student@example.com"  # normalised
        assert user.role == User.Role.PORTAL
        assert user.is_portal_user and not user.is_admin
        assert not user.has_usable_password()
        assert not user.is_staff

    def test_create_user_with_phone_only(self):
        user = User.objects.create_user(phone="+919876543210")

        assert user.phone == "+919876543210"
        assert user.email is None

    def test_user_requires_email_or_phone(self):
        with pytest.raises(ValueError):
            User.objects.create_user()

    def test_db_constraint_rejects_user_without_email_and_phone(self):
        with pytest.raises(IntegrityError):
            User.objects.bulk_create([User()])  # bypasses manager validation

    def test_email_is_unique_case_insensitively(self):
        User.objects.create_user(email="a@example.com")
        with pytest.raises(ValidationError):
            User.objects.create_user(email="A@EXAMPLE.COM")

    def test_phone_is_unique(self):
        User.objects.create_user(phone="+919876543210")
        with pytest.raises(ValidationError):
            User.objects.create_user(phone="+919876543210")

    def test_invalid_phone_format_rejected(self):
        with pytest.raises(ValidationError):
            User.objects.create_user(phone="98765")

    def test_multiple_phone_only_users_allowed(self):
        # NULL emails must not collide with each other.
        User.objects.create_user(phone="+919876543210")
        User.objects.create_user(phone="+919876543211")
        assert User.objects.filter(email__isnull=True).count() == 2

    def test_create_superuser_is_admin_with_password(self):
        admin = User.objects.create_superuser(
            email="admin@example.com", password="a-strong-pass-123"
        )

        assert admin.role == User.Role.ADMIN
        assert admin.is_staff and admin.is_superuser
        assert admin.check_password("a-strong-pass-123")

    def test_create_superuser_rejects_non_admin_role(self):
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email="x@example.com", password="pw-123456789", role=User.Role.PORTAL
            )

    def test_ids_are_integers(self):
        user = User.objects.create_user(email="u@example.com")
        assert isinstance(user.id, int)

    def test_soft_deleted_user_hidden_from_default_manager(self):
        user = User.objects.create_user(email="gone@example.com")
        user.soft_delete()

        assert not User.objects.filter(pk=user.pk).exists()
        assert User.all_objects.get(pk=user.pk).deleted_at is not None

    def test_soft_deleted_user_still_blocks_email_reuse(self):
        # History is preserved, so the identity can't be silently re-created.
        User.objects.create_user(email="gone@example.com").soft_delete()
        with pytest.raises(ValidationError):
            User.objects.create_user(email="gone@example.com")
