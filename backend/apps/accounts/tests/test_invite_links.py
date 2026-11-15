"""The "Set your password" link in invite emails: single use, expiring, hashed."""

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import InviteLink, User
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog

USERS = "/api/v1/admin/users/"
CHECK = "/api/v1/auth/invite/check/"
ACCEPT = "/api/v1/auth/invite/accept/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
PASSWORD = "Sai-Tuitions-Rocks-42"


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return c


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


def invite(admin, email="meera@example.com", **extra):
    response = client_for(admin).post(
        USERS,
        {
            "first_name": "Meera",
            "last_name": "Joshi",
            "role": "TEACHER",
            "email": email,
            **extra,
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    return User.objects.get(email=email)


def link_token() -> str:
    body = mail.outbox[-1].body
    return re.search(r"/set-password\?token=([\w-]+)", body).group(1)


@pytest.mark.django_db
class TestInviteEmail:
    def test_email_has_a_single_use_link_and_matching_wording(self, admin):
        invite(admin)
        body = " ".join(mail.outbox[-1].body.split())  # ignore line wrapping
        assert "http://localhost:5173/set-password?token=" in body
        assert "7 days" in body
        # The same words as the button on the login page.
        assert '"First time here, or forgot your password?"' in body
        assert '"Continue with Google"' in body
        # Only the hash is stored, never the token itself.
        raw = link_token()
        assert not InviteLink.objects.filter(token_hash=raw).exists()
        assert InviteLink.objects.count() == 1

    def test_resending_cancels_the_old_link(self, admin):
        user = invite(admin)
        old = link_token()
        client_for(admin).post(f"{USERS}{user.pk}/resend-invite/", format="json")
        new = link_token()
        assert old != new
        assert APIClient().post(CHECK, {"token": old}, format="json").status_code == 400
        assert APIClient().post(CHECK, {"token": new}, format="json").status_code == 200


@pytest.mark.django_db
class TestAcceptingTheInvite:
    def test_check_greets_them_and_accept_sets_the_password(self, admin):
        user = invite(admin)
        token = link_token()
        browser = APIClient()

        info = browser.post(CHECK, {"token": token}, format="json").json()["data"]
        assert info == {"first_name": "Meera", "email": "meera@example.com"}

        accepted = browser.post(
            ACCEPT, {"token": token, "new_password": PASSWORD}, format="json"
        )
        assert accepted.status_code == 200
        assert accepted.json()["data"]["email"] == "meera@example.com"
        assert "access" not in accepted.json()["data"]  # not logged in yet
        user.refresh_from_db()
        assert user.check_password(PASSWORD)
        assert user.email_verified_at is not None
        assert AuditLog.objects.filter(
            action="INVITE_ACCEPTED", target_id=str(user.pk)
        ).exists()

        # The link proved the inbox, so this browser signs in without a code.
        mail.outbox.clear()
        login = browser.post(
            LOGIN, {"email": "meera@example.com", "password": PASSWORD}, format="json"
        )
        assert login.json()["data"]["status"] == "AUTHENTICATED"
        assert mail.outbox == []

    def test_a_link_works_once(self, admin):
        invite(admin)
        token = link_token()
        APIClient().post(
            ACCEPT, {"token": token, "new_password": PASSWORD}, format="json"
        )
        again = APIClient().post(
            ACCEPT, {"token": token, "new_password": PASSWORD}, format="json"
        )
        assert again.status_code == 400
        assert again.json()["error_code"] == "INVITE_LINK_INVALID"

    def test_an_expired_link_fails(self, admin):
        invite(admin)
        token = link_token()
        InviteLink.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        response = APIClient().post(CHECK, {"token": token}, format="json")
        assert response.json()["error_code"] == "INVITE_LINK_INVALID"

    def test_unknown_tokens_get_the_same_answer(self, db):
        response = APIClient().post(CHECK, {"token": "made-up"}, format="json")
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVITE_LINK_INVALID"

    def test_a_weak_password_keeps_the_link_usable(self, admin):
        invite(admin)
        token = link_token()
        weak = APIClient().post(
            ACCEPT, {"token": token, "new_password": "12345678"}, format="json"
        )
        assert weak.status_code == 400
        assert (
            APIClient().post(CHECK, {"token": token}, format="json").status_code == 200
        )

    def test_a_deactivated_person_cannot_use_their_link(self, admin):
        user = invite(admin)
        token = link_token()
        client_for(admin).post(f"{USERS}{user.pk}/deactivate/", format="json")
        response = APIClient().post(CHECK, {"token": token}, format="json")
        assert response.status_code == 403


@pytest.mark.django_db
def test_logging_in_another_way_first_uses_the_link_up(admin):
    """E.g. Continue with Google: any first login spends the invite link."""
    user = invite(admin)
    token = link_token()
    issue_tokens(user)  # what every successful login does
    response = APIClient().post(CHECK, {"token": token}, format="json")
    assert response.json()["error_code"] == "INVITE_LINK_INVALID"


@pytest.mark.django_db
def test_me_says_whether_a_password_is_set(admin):
    google_only = invite(admin)
    assert client_for(google_only).get(ME).json()["data"]["has_password"] is False
    google_only.set_password(PASSWORD)
    google_only.save()
    assert client_for(google_only).get(ME).json()["data"]["has_password"] is True
