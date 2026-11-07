"""Invite-only onboarding: admins create logins; people log in; names come from the invite."""

import re
from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services.otp_delivery import OTPDeliveryError
from apps.accounts.services.sms import LocmemSMSBackend
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog

USERS_URL = "/api/v1/admin/users/"
ME_URL = "/api/v1/auth/me/"
OTP_REQUEST_URL = "/api/v1/auth/otp/request/"
OTP_VERIFY_URL = "/api/v1/auth/otp/verify/"


def client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def new_login(**overrides):
    return {
        "first_name": "Priya",
        "last_name": "Shah",
        "role": "PORTAL",
        "phone": "98765 43210",
        "email": "Priya@Example.com",
        **overrides,
    }


@pytest.fixture
def owner(db):
    return User.objects.create_superuser(email="owner@example.com", password="x" * 12)


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com", role=User.Role.ADMIN, first_name="Asha"
    )


@pytest.mark.django_db
class TestCreateLogin:
    def test_admin_creates_portal_login_and_invite_goes_by_sms_and_email(self, admin):
        response = client_for(admin).post(USERS_URL, new_login(), format="json")

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["invite_sent"] == {"email": True, "phone": True}
        user = User.objects.get(phone="+919876543210")
        assert user.email == "priya@example.com"
        assert (user.first_name, user.last_name, user.role) == (
            "Priya",
            "Shah",
            "PORTAL",
        )
        assert user.invited_by == admin
        assert user.activated_at is None
        assert data["user"]["invite_accepted"] is False

        assert mail.outbox[-1].to == ["priya@example.com"]
        assert "added to" in mail.outbox[-1].subject
        assert LocmemSMSBackend.outbox[-1]["to"] == "+919876543210"
        assert "Hi Priya" in LocmemSMSBackend.outbox[-1]["message"]
        assert not re.search(r"\b\d{6}\b", mail.outbox[-1].body)  # no code in invites

        log = AuditLog.objects.get(action="USER_INVITED")
        assert log.actor == admin and log.target_id == str(user.pk)

    def test_invited_person_logs_in_without_entering_their_name(self, admin):
        client_for(admin).post(USERS_URL, new_login(email=""), format="json")
        body = {"channel": "PHONE", "identifier": "+919876543210"}
        APIClient().post(OTP_REQUEST_URL, body, format="json")
        code = re.search(r"\b(\d{6})\b", LocmemSMSBackend.outbox[-1]["message"]).group(
            1
        )

        response = APIClient().post(
            OTP_VERIFY_URL, {**body, "code": code}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["data"]["user"]["first_name"] == "Priya"
        assert User.objects.get(phone="+919876543210").activated_at is not None

    def test_admin_creates_teacher(self, admin):
        response = client_for(admin).post(
            USERS_URL,
            new_login(role="TEACHER", phone="", email="t@example.com"),
            format="json",
        )
        assert response.status_code == 201
        assert User.objects.get(email="t@example.com").role == User.Role.TEACHER

    def test_admin_cannot_create_admin(self, admin):
        response = client_for(admin).post(
            USERS_URL, new_login(role="ADMIN"), format="json"
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "OWNER_REQUIRED"
        assert not User.objects.filter(phone="+919876543210").exists()

    def test_owner_can_create_admin(self, owner):
        response = client_for(owner).post(
            USERS_URL, new_login(role="ADMIN"), format="json"
        )
        assert response.status_code == 201

    @pytest.mark.parametrize("role", [User.Role.TEACHER, User.Role.PORTAL])
    def test_non_admins_cannot_create_logins(self, role):
        actor = User.objects.create_user(email="actor@example.com", role=role)
        response = client_for(actor).post(USERS_URL, new_login(), format="json")
        assert response.status_code == 403

    def test_duplicate_contact_rejected_with_field_detail(self, admin):
        User.objects.create_user(phone="+919876543210")
        response = client_for(admin).post(USERS_URL, new_login(), format="json")
        assert response.status_code == 409
        assert response.json()["error_code"] == "CONTACT_IN_USE"
        assert "phone" in response.json()["errors"]

    def test_needs_email_or_phone(self, admin):
        response = client_for(admin).post(
            USERS_URL, new_login(email="", phone=""), format="json"
        )
        assert response.status_code == 400

    def test_names_required(self, admin):
        response = client_for(admin).post(
            USERS_URL, new_login(first_name="", last_name=""), format="json"
        )
        assert set(response.json()["errors"]) >= {"first_name", "last_name"}

    def test_invalid_phone(self, admin):
        response = client_for(admin).post(
            USERS_URL, new_login(phone="123"), format="json"
        )
        assert response.status_code == 400
        assert "phone" in response.json()["errors"]

    def test_delivery_failure_keeps_the_login_and_reports_it(self, admin):
        with mock.patch(
            "apps.accounts.services.users.deliver_invite", side_effect=OTPDeliveryError
        ):
            response = client_for(admin).post(USERS_URL, new_login(), format="json")

        assert response.status_code == 201
        assert response.json()["data"]["invite_sent"] == {
            "email": False,
            "phone": False,
        }
        assert User.objects.filter(phone="+919876543210").exists()


@pytest.mark.django_db
class TestResendInvite:
    def test_resend_before_first_login(self, admin):
        user = User.objects.create_user(email="p@example.com", first_name="P")
        response = client_for(admin).post(f"{USERS_URL}{user.pk}/resend-invite/")
        assert response.status_code == 200
        assert response.json()["data"]["invite_sent"] == {"email": True}

    def test_no_resend_after_first_login(self, admin):
        user = User.objects.create_user(email="p@example.com")
        issue_tokens(user)  # logged in once
        response = client_for(admin).post(f"{USERS_URL}{user.pk}/resend-invite/")
        assert response.json()["error_code"] == "INVITE_ALREADY_ACCEPTED"


@pytest.mark.django_db
class TestNames:
    def test_user_edits_own_name(self):
        user = User.objects.create_user(email="p@example.com", first_name="Pri")
        response = client_for(user).patch(
            ME_URL, {"first_name": "Priya"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["data"]["first_name"] == "Priya"
        assert AuditLog.objects.get(action="USER_UPDATED").changes == {
            "first_name": ["Pri", "Priya"]
        }

    def test_admin_fixes_a_name(self, admin):
        user = User.objects.create_user(email="p@example.com", last_name="Sha")
        response = client_for(admin).patch(
            f"{USERS_URL}{user.pk}/", {"last_name": "Shah"}, format="json"
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.last_name == "Shah"

    def test_admin_cannot_rename_another_admin(self, admin):
        other = User.objects.create_user(email="a2@example.com", role=User.Role.ADMIN)
        response = client_for(admin).patch(
            f"{USERS_URL}{other.pk}/", {"first_name": "X"}, format="json"
        )
        assert response.json()["error_code"] == "OWNER_REQUIRED"

    def test_no_change_writes_no_audit(self):
        user = User.objects.create_user(email="p@example.com", first_name="P")
        client_for(user).patch(ME_URL, {"first_name": "P"}, format="json")
        assert not AuditLog.objects.exists()
