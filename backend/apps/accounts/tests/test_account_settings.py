"""Account settings: verified add/change/remove of email & phone, and admin recovery."""

import re

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services.sms import LocmemSMSBackend
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog

CONTACT_URL = "/api/v1/auth/me/contact/"
VERIFY_URL = "/api/v1/auth/me/contact/verify/"
OTP_REQUEST_URL = "/api/v1/auth/otp/request/"
OTP_VERIFY_URL = "/api/v1/auth/otp/verify/"
ADMIN_USERS_URL = "/api/v1/admin/users/"

PHONE = "+919876543210"


def client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def last_sms_code():
    return re.search(r"\b(\d{6})\b", LocmemSMSBackend.outbox[-1]["message"]).group(1)


def last_email_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


@pytest.fixture
def student(db):
    return User.objects.create_user(email="student@example.com")


@pytest.mark.django_db
class TestAddAndChange:
    def test_add_phone_with_verification_then_phone_login_works(self, student):
        client = client_for(student)

        response = client.post(
            CONTACT_URL,
            {"channel": "PHONE", "identifier": "98765 43210"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["data"]["sent_to"] == "+91******3210"
        assert LocmemSMSBackend.outbox[-1]["to"] == PHONE

        response = client.post(
            VERIFY_URL,
            {"channel": "PHONE", "identifier": PHONE, "code": last_sms_code()},
            format="json",
        )
        assert response.status_code == 200
        student.refresh_from_db()
        assert student.phone == PHONE
        assert student.phone_verified_at is not None
        assert AuditLog.objects.get(action="CONTACT_CHANGED").changes["phone"] == [
            None,
            PHONE,
        ]

        # The new phone now works for OTP login.
        cache.clear()
        body = {"channel": "PHONE", "identifier": PHONE, "purpose": "LOGIN"}
        APIClient().post(OTP_REQUEST_URL, body, format="json")
        login = APIClient().post(
            OTP_VERIFY_URL, {**body, "code": last_sms_code()}, format="json"
        )
        assert login.status_code == 200
        assert login.json()["data"]["user"]["id"] == student.id

    def test_change_email_notifies_old_address(
        self, student, django_capture_on_commit_callbacks
    ):
        client = client_for(student)
        client.post(
            CONTACT_URL,
            {"channel": "EMAIL", "identifier": "New@Example.com"},
            format="json",
        )
        assert mail.outbox[-1].to == ["new@example.com"]

        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(
                VERIFY_URL,
                {
                    "channel": "EMAIL",
                    "identifier": "new@example.com",
                    "code": last_email_code(),
                },
                format="json",
            )

        assert response.status_code == 200
        student.refresh_from_db()
        assert student.email == "new@example.com"
        notice = mail.outbox[-1]
        assert notice.to == ["student@example.com"]
        assert "n*w@example.com" in notice.body

    def test_old_email_no_longer_logs_in(self, student):
        client = client_for(student)
        client.post(
            CONTACT_URL,
            {"channel": "EMAIL", "identifier": "new@example.com"},
            format="json",
        )
        client.post(
            VERIFY_URL,
            {
                "channel": "EMAIL",
                "identifier": "new@example.com",
                "code": last_email_code(),
            },
            format="json",
        )
        mail.outbox.clear()
        cache.clear()

        APIClient().post(
            OTP_REQUEST_URL,
            {
                "channel": "EMAIL",
                "identifier": "student@example.com",
                "purpose": "LOGIN",
            },
            format="json",
        )
        assert mail.outbox == []  # nothing sent: no account has that email any more

    def test_same_value_rejected(self, student):
        response = client_for(student).post(
            CONTACT_URL,
            {"channel": "EMAIL", "identifier": "student@example.com"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "CONTACT_UNCHANGED"

    def test_value_owned_by_another_account_rejected(self, student):
        User.objects.create_user(phone=PHONE)
        response = client_for(student).post(
            CONTACT_URL, {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        assert response.status_code == 409
        assert response.json()["error_code"] == "CONTACT_IN_USE"
        assert LocmemSMSBackend.outbox == []

    def test_taken_between_request_and_verify(self, student):
        client = client_for(student)
        client.post(
            CONTACT_URL, {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        code = last_sms_code()
        User.objects.create_user(phone=PHONE)  # someone registers it meanwhile

        response = client.post(
            VERIFY_URL,
            {"channel": "PHONE", "identifier": PHONE, "code": code},
            format="json",
        )
        assert response.status_code == 409
        student.refresh_from_db()
        assert student.phone is None

    def test_wrong_code_changes_nothing(self, student):
        client = client_for(student)
        client.post(
            CONTACT_URL, {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        code = last_sms_code()

        response = client.post(
            VERIFY_URL,
            {
                "channel": "PHONE",
                "identifier": PHONE,
                "code": "000000" if code != "000000" else "111111",
            },
            format="json",
        )
        assert response.json()["error_code"] == "OTP_INVALID"
        student.refresh_from_db()
        assert student.phone is None

    def test_code_bound_to_the_requesting_user(self, student):
        """Another user can't finish a change with a code requested by someone else."""
        other = User.objects.create_user(email="other@example.com")
        client_for(student).post(
            CONTACT_URL, {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        code = last_sms_code()

        response = client_for(other).post(
            VERIFY_URL,
            {"channel": "PHONE", "identifier": PHONE, "code": code},
            format="json",
        )
        assert response.json()["error_code"] == "OTP_INVALID"
        assert not User.objects.filter(phone=PHONE).exists()

    def test_login_code_cannot_be_used_to_change_contact(self, student):
        User.objects.create_user(phone="+919999999999")
        APIClient().post(
            OTP_REQUEST_URL,
            {"channel": "PHONE", "identifier": "+919999999999", "purpose": "LOGIN"},
            format="json",
        )
        response = client_for(student).post(
            VERIFY_URL,
            {
                "channel": "PHONE",
                "identifier": "+919999999999",
                "code": last_sms_code(),
            },
            format="json",
        )
        assert response.json()["error_code"] == "OTP_INVALID"

    def test_requires_authentication(self):
        assert APIClient().post(CONTACT_URL, {}, format="json").status_code == 401

    def test_invalid_phone(self, student):
        response = client_for(student).post(
            CONTACT_URL, {"channel": "PHONE", "identifier": "123"}, format="json"
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestRemove:
    def test_remove_phone_when_email_remains(self, student):
        student.phone = PHONE
        student.save()

        response = client_for(student).delete(f"{CONTACT_URL}phone/")

        assert response.status_code == 200
        student.refresh_from_db()
        assert student.phone is None and student.phone_verified_at is None
        assert AuditLog.objects.filter(action="CONTACT_REMOVED").exists()

    def test_cannot_remove_last_contact_method(self, student):
        response = client_for(student).delete(f"{CONTACT_URL}email/")
        assert response.status_code == 400
        assert response.json()["error_code"] == "LAST_CONTACT_METHOD"

    def test_remove_missing(self, student):
        response = client_for(student).delete(f"{CONTACT_URL}phone/")
        assert response.json()["error_code"] == "CONTACT_NOT_SET"

    def test_unknown_kind_404(self, student):
        assert client_for(student).delete(f"{CONTACT_URL}fax/").status_code == 404


@pytest.mark.django_db
class TestAdminRecovery:
    @pytest.fixture
    def admin(self, db):
        return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)

    def url(self, user):
        return f"{ADMIN_USERS_URL}{user.pk}/contact/"

    def test_admin_sets_new_email_unverified(self, admin, student):
        response = client_for(admin).post(
            self.url(student),
            {"channel": "EMAIL", "identifier": "fixed@example.com"},
            format="json",
        )

        assert response.status_code == 200
        student.refresh_from_db()
        assert student.email == "fixed@example.com"
        assert student.email_verified_at is None
        log = AuditLog.objects.get(action="CONTACT_CHANGED")
        assert log.actor_id == admin.pk and log.changes["by_admin"] is True

    def test_verified_on_first_otp_login(self, admin, student):
        client_for(admin).post(
            self.url(student), {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        body = {"channel": "PHONE", "identifier": PHONE, "purpose": "LOGIN"}
        APIClient().post(OTP_REQUEST_URL, body, format="json")
        APIClient().post(
            OTP_VERIFY_URL, {**body, "code": last_sms_code()}, format="json"
        )

        student.refresh_from_db()
        assert student.phone_verified_at is not None

    def test_admin_removes_contact(self, admin, student):
        student.phone = PHONE
        student.save()
        response = client_for(admin).post(
            self.url(student), {"channel": "EMAIL", "identifier": None}, format="json"
        )
        assert response.status_code == 200
        student.refresh_from_db()
        assert student.email is None

    def test_admin_cannot_remove_last_contact(self, admin, student):
        response = client_for(admin).post(
            self.url(student), {"channel": "EMAIL", "identifier": None}, format="json"
        )
        assert response.json()["error_code"] == "LAST_CONTACT_METHOD"

    def test_admin_cannot_edit_own_contact_here(self, admin):
        response = client_for(admin).post(
            self.url(admin), {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        assert response.json()["error_code"] == "CANNOT_MODIFY_SELF"

    def test_plain_admin_cannot_edit_another_admin(self, admin):
        other = User.objects.create_user(
            email="admin2@example.com", role=User.Role.ADMIN
        )
        response = client_for(admin).post(
            self.url(other), {"channel": "PHONE", "identifier": PHONE}, format="json"
        )
        assert response.json()["error_code"] == "OWNER_REQUIRED"

    def test_student_cannot_use_admin_endpoint(self, student):
        other = User.objects.create_user(email="other@example.com")
        response = client_for(student).post(
            self.url(other),
            {"channel": "EMAIL", "identifier": "x@example.com"},
            format="json",
        )
        assert response.status_code == 403
        other.refresh_from_db()
        assert other.email == "other@example.com"

    def test_duplicate_rejected(self, admin, student):
        User.objects.create_user(email="taken@example.com")
        response = client_for(admin).post(
            self.url(student),
            {"channel": "EMAIL", "identifier": "taken@example.com"},
            format="json",
        )
        assert response.status_code == 409
