"""
While SMS is off (production's DisabledSMSBackend), every login must keep an
email: otherwise it has no way to receive a sign-in code. With SMS on
(development/tests use console/locmem backends), phone-only logins are fine.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services.sms import sms_enabled
from apps.accounts.services.tokens import issue_tokens

USERS_URL = "/api/v1/admin/users/"
CONTACT_URL = "/api/v1/auth/me/contact/"
DISABLED = "apps.accounts.services.sms.DisabledSMSBackend"
PHONE = "+919000000009"


def client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def sms_off(settings):
    settings.SMS_BACKEND = DISABLED


def test_sms_enabled_follows_the_backend(settings):
    assert sms_enabled()  # tests run with the locmem backend
    settings.SMS_BACKEND = DISABLED
    assert not sms_enabled()


@pytest.mark.django_db
class TestInviteNeedsEmail:
    def invite(self, admin, **contact):
        body = {"role": "PORTAL", "first_name": "Priya", "last_name": "Shah", **contact}
        return client_for(admin).post(USERS_URL, body, format="json")

    def test_phone_only_invite_rejected_when_sms_off(self, admin, sms_off):
        response = self.invite(admin, phone=PHONE)
        assert response.status_code == 400
        assert "SMS isn't enabled" in response.json()["errors"]["email"][0]
        assert not User.objects.filter(phone=PHONE).exists()

    def test_email_plus_phone_accepted_when_sms_off(self, admin, sms_off):
        response = self.invite(admin, email="priya@example.com", phone=PHONE)
        assert response.status_code == 201, response.json()
        user = User.objects.get(email="priya@example.com")
        assert user.phone == PHONE  # kept, ready for when SMS is switched on

    def test_phone_only_invite_fine_when_sms_on(self, admin):
        assert self.invite(admin, phone=PHONE).status_code == 201


@pytest.mark.django_db
class TestCannotDropEmail:
    @pytest.fixture
    def parent(self, db):
        return User.objects.create_user(email="parent@example.com", phone=PHONE)

    def test_self_service_email_removal_blocked_when_sms_off(self, parent, sms_off):
        response = client_for(parent).delete(f"{CONTACT_URL}email/")
        assert response.status_code == 400
        assert response.json()["error_code"] == "EMAIL_REQUIRED"
        parent.refresh_from_db()
        assert parent.email == "parent@example.com"

    def test_admin_email_removal_blocked_when_sms_off(self, admin, parent, sms_off):
        response = client_for(admin).post(
            f"{USERS_URL}{parent.pk}/contact/",
            {"channel": "EMAIL", "identifier": None},
            format="json",
        )
        assert response.json()["error_code"] == "EMAIL_REQUIRED"

    def test_phone_can_still_be_removed_when_sms_off(self, parent, sms_off):
        response = client_for(parent).delete(f"{CONTACT_URL}phone/")
        assert response.status_code == 200

    def test_email_removal_allowed_when_sms_on(self, parent):
        response = client_for(parent).delete(f"{CONTACT_URL}email/")
        assert response.status_code == 200
