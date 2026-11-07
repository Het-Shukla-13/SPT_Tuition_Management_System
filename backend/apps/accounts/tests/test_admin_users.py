"""Admin user-management API: role gates, self-protection, last-admin rule, audit trail."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.exceptions import LastAdminProtected
from apps.accounts.models import User, UserSession
from apps.accounts.services.tokens import issue_tokens
from apps.accounts.services.users import change_role
from apps.audit.models import AuditLog

USERS_URL = "/api/v1/admin/users/"
ME_URL = "/api/v1/auth/me/"


def client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def url(user, action=""):
    return f"{USERS_URL}{user.pk}/{action + '/' if action else ''}"


@pytest.fixture
def owner(db):
    return User.objects.create_superuser(email="owner@example.com", password="x" * 12)


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def student(db):
    return User.objects.create_user(email="student@example.com")


@pytest.mark.django_db
class TestAccessControl:
    def test_anonymous_gets_401(self):
        assert APIClient().get(USERS_URL).status_code == 401

    def test_student_gets_403(self, student):
        response = client_for(student).get(USERS_URL)
        assert response.status_code == 403
        assert response.json()["error_code"] == "PERMISSION_DENIED"

    def test_student_cannot_change_roles_or_status(self, student, admin):
        client = client_for(student)
        assert client.post(url(admin, "deactivate")).status_code == 403
        assert (
            client.post(
                url(student, "role"), {"role": "ADMIN"}, format="json"
            ).status_code
            == 403
        )
        student.refresh_from_db()
        assert student.role == User.Role.STUDENT

    def test_plain_admin_cannot_change_roles(self, admin, student):
        response = client_for(admin).post(
            url(student, "role"), {"role": "ADMIN"}, format="json"
        )
        assert response.status_code == 403
        student.refresh_from_db()
        assert student.role == User.Role.STUDENT


@pytest.mark.django_db
class TestListAndDetail:
    def test_list_is_paginated_with_meta(self, admin, student):
        response = client_for(admin).get(USERS_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["total_count"] == 2
        assert body["meta"]["page"] == 1
        assert {u["email"] for u in body["data"]} == {
            "admin@example.com",
            "student@example.com",
        }

    def test_filter_search_and_ordering(self, admin, student):
        client = client_for(admin)
        User.objects.create_user(phone="+919876543210")

        students = client.get(USERS_URL, {"role": "STUDENT"}).json()["data"]
        assert len(students) == 2

        found = client.get(USERS_URL, {"search": "98765"}).json()["data"]
        assert [u["phone"] for u in found] == ["+919876543210"]

        User.objects.create_user(email="aaa@example.com")
        ordered = client.get(
            USERS_URL, {"ordering": "email", "role": "STUDENT", "search": "example.com"}
        ).json()["data"]
        assert [u["email"] for u in ordered] == [
            "aaa@example.com",
            "student@example.com",
        ]

        inactive = client.get(USERS_URL, {"is_active": "false"}).json()["data"]
        assert inactive == []

    def test_page_size_capped(self, admin):
        response = client_for(admin).get(USERS_URL, {"page_size": 10_000})
        assert response.json()["meta"]["page_size"] == 100

    def test_soft_deleted_users_hidden(self, admin, student):
        student.soft_delete()
        client = client_for(admin)
        assert client.get(url(student)).status_code == 404
        assert client.get(USERS_URL).json()["meta"]["total_count"] == 1

    def test_detail(self, admin, student):
        response = client_for(admin).get(url(student))
        assert response.status_code == 200
        assert response.json()["data"]["email"] == "student@example.com"


@pytest.mark.django_db
class TestActivation:
    def test_deactivate_student_ends_sessions_and_audits(self, admin, student):
        student_client = client_for(student)
        assert student_client.get(ME_URL).status_code == 200

        response = client_for(admin).post(url(student, "deactivate"))

        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False
        assert student_client.get(ME_URL).status_code == 401
        assert not UserSession.objects.active().filter(user=student).exists()
        assert (
            UserSession.objects.get(user=student).revoked_reason
            == "ACCOUNT_DEACTIVATED"
        )
        log = AuditLog.objects.get(action="USER_DEACTIVATED")
        assert (log.actor_id, log.target_id) == (admin.pk, str(student.pk))
        assert log.changes == {"is_active": [True, False]}

    def test_deactivate_is_idempotent(self, admin, student):
        client = client_for(admin)
        client.post(url(student, "deactivate"))
        assert client.post(url(student, "deactivate")).status_code == 200
        assert AuditLog.objects.filter(action="USER_DEACTIVATED").count() == 1

    def test_reactivate(self, admin, student):
        client = client_for(admin)
        client.post(url(student, "deactivate"))

        response = client.post(url(student, "activate"))

        assert response.json()["data"]["is_active"] is True
        assert AuditLog.objects.filter(action="USER_ACTIVATED").count() == 1

    def test_cannot_deactivate_self(self, admin):
        response = client_for(admin).post(url(admin, "deactivate"))
        assert response.status_code == 403
        assert response.json()["error_code"] == "CANNOT_MODIFY_SELF"

    def test_admin_cannot_deactivate_another_admin(self, admin):
        other = User.objects.create_user(
            email="admin2@example.com", role=User.Role.ADMIN
        )
        response = client_for(admin).post(url(other, "deactivate"))
        assert response.status_code == 403
        assert response.json()["error_code"] == "OWNER_REQUIRED"

    def test_owner_can_deactivate_an_admin(self, owner, admin):
        assert client_for(owner).post(url(admin, "deactivate")).status_code == 200


@pytest.mark.django_db
class TestRoleChange:
    def test_owner_promotes_student_and_their_sessions_end(self, owner, student):
        student_client = client_for(student)

        response = client_for(owner).post(
            url(student, "role"), {"role": "ADMIN"}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["data"]["role"] == "ADMIN"
        assert student_client.get(ME_URL).status_code == 401  # must log in again
        log = AuditLog.objects.get(action="USER_ROLE_CHANGED")
        assert log.changes == {"role": ["STUDENT", "ADMIN"]}
        assert log.actor_id == owner.pk

    def test_owner_demotes_admin(self, owner, admin):
        response = client_for(owner).post(
            url(admin, "role"), {"role": "STUDENT"}, format="json"
        )
        assert response.status_code == 200
        admin.refresh_from_db()
        assert admin.role == User.Role.STUDENT

    def test_owner_cannot_change_own_role(self, owner):
        response = client_for(owner).post(
            url(owner, "role"), {"role": "STUDENT"}, format="json"
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "CANNOT_MODIFY_SELF"

    def test_invalid_role_rejected(self, owner, student):
        response = client_for(owner).post(
            url(student, "role"), {"role": "GOD"}, format="json"
        )
        assert response.status_code == 400

    def test_last_active_admin_cannot_be_demoted(self, owner):
        # The owner is the only admin; another superuser-less actor demoting
        # them must be refused (exercised at the service layer).
        actor = User.objects.create_user(email="ops@example.com")
        with pytest.raises(LastAdminProtected):
            change_role(actor=actor, target=owner, role=User.Role.STUDENT)
        owner.refresh_from_db()
        assert owner.role == User.Role.ADMIN
