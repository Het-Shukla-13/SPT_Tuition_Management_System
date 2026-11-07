from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.common.permissions import IsAdmin, IsOwnerOrAdmin, IsStudent, IsSuperUser

factory = APIRequestFactory()


def request_for(user):
    request = factory.get("/anything/")
    request.user = user
    return request


@pytest.fixture
def student(db):
    return User.objects.create_user(email="student@example.com")


@pytest.fixture
def other_student(db):
    return User.objects.create_user(email="other@example.com")


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def owner(db):
    return User.objects.create_superuser(email="owner@example.com", password="x" * 12)


@pytest.mark.django_db
class TestRolePermissions:
    @pytest.mark.parametrize(
        "permission, who, expected",
        [
            (IsAdmin, "admin", True),
            (IsAdmin, "student", False),
            (IsStudent, "student", True),
            (IsStudent, "admin", False),
            (IsSuperUser, "owner", True),
            (IsSuperUser, "admin", False),
            (IsSuperUser, "student", False),
        ],
    )
    def test_role_matrix(self, request, permission, who, expected):
        user = request.getfixturevalue(who)
        assert permission().has_permission(request_for(user), view=None) is expected

    @pytest.mark.parametrize("permission", [IsAdmin, IsStudent, IsSuperUser])
    def test_anonymous_always_denied(self, permission):
        assert (
            permission().has_permission(request_for(AnonymousUser()), view=None)
            is False
        )

    def test_inactive_admin_denied(self, admin):
        admin.is_active = False
        assert IsAdmin().has_permission(request_for(admin), view=None) is False

    def test_superuser_demoted_to_student_loses_owner_powers(self, owner):
        owner.role = User.Role.STUDENT
        assert IsSuperUser().has_permission(request_for(owner), view=None) is False


@pytest.mark.django_db
class TestIsOwnerOrAdmin:
    def check(self, user, obj, owner_field="user"):
        view = SimpleNamespace(owner_field=owner_field)
        return IsOwnerOrAdmin().has_object_permission(request_for(user), view, obj)

    def test_owner_allowed(self, student):
        assert self.check(student, SimpleNamespace(user=student)) is True

    def test_other_student_denied(self, student, other_student):
        assert self.check(other_student, SimpleNamespace(user=student)) is False

    def test_admin_allowed_on_anything(self, admin, student):
        assert self.check(admin, SimpleNamespace(user=student)) is True

    def test_nested_owner_path(self, student, other_student):
        record = SimpleNamespace(student=SimpleNamespace(user=student))
        assert self.check(student, record, owner_field="student.user") is True
        assert self.check(other_student, record, owner_field="student.user") is False

    def test_user_object_must_be_self(self, student, other_student):
        assert self.check(student, student) is True
        assert self.check(student, other_student) is False

    def test_missing_owner_denied(self, student):
        assert self.check(student, SimpleNamespace(user=None)) is False
        assert self.check(student, SimpleNamespace()) is False
