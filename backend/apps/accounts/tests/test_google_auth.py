"""
Google Sign-In (option C): email OTP on first link, one-click afterwards.

Google's own signature/expiry/audience check (verify_oauth2_token) is mocked;
everything we do with its result (issuer, email_verified, linking rules) runs
for real.
"""

import re
from unittest import mock

import pytest
from django.core import mail
from django.core.cache import cache
from google.auth import exceptions as google_exceptions
from rest_framework.test import APIClient

from apps.accounts.models import User, UserSession
from apps.audit.models import AuditLog

GOOGLE_URL = "/api/v1/auth/google/"
VERIFY_URL = "/api/v1/auth/google/verify/"
UNLINK_URL = "/api/v1/auth/google/unlink/"
OTP_REQUEST_URL = "/api/v1/auth/otp/request/"
ME_URL = "/api/v1/auth/me/"

ALICE = {
    "iss": "https://accounts.google.com",
    "sub": "google-sub-alice",
    "email": "alice@gmail.com",
    "email_verified": True,
}
# A different Google account claiming the same email address.
IMPOSTOR = {**ALICE, "sub": "google-sub-impostor"}

TOKENS = {"tok-alice": ALICE, "tok-impostor": IMPOSTOR}


def fake_verify(token, request, audience=None):
    if token not in TOKENS:
        raise ValueError("Token used too late / wrong audience / bad signature")
    return dict(TOKENS[token])


@pytest.fixture(autouse=True)
def google(monkeypatch):
    patcher = mock.patch(
        "google.oauth2.id_token.verify_oauth2_token", side_effect=fake_verify
    )
    with patcher as mocked:
        yield mocked


def start(client, token="tok-alice"):
    return client.post(GOOGLE_URL, {"id_token": token}, format="json")


def verify(client, code, token="tok-alice"):
    return client.post(VERIFY_URL, {"id_token": token, "code": code}, format="json")


def emailed_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def first_google_login(client=None, token="tok-alice"):
    client = client or APIClient()
    assert start(client, token).json()["data"]["status"] == "OTP_REQUIRED"
    response = verify(client, emailed_code(), token)
    assert response.status_code == 200, response.json()
    cache.clear()  # resend cooldown
    return response.json()["data"]


@pytest.mark.django_db
class TestFirstGoogleLogin:
    def test_new_user_needs_otp_then_is_created_and_linked(self):
        client = APIClient()

        response = start(client)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "OTP_REQUIRED"
        assert data["email"] == "a***e@gmail.com"
        assert "access" not in data
        assert mail.outbox[-1].to == ["alice@gmail.com"]
        assert not User.objects.exists()

        response = verify(client, emailed_code())

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "AUTHENTICATED"
        assert data["access"] and data["refresh"]
        user = User.objects.get(email="alice@gmail.com")
        assert user.google_id == "google-sub-alice"
        assert user.role == User.Role.STUDENT
        assert user.email_verified_at is not None
        assert data["user"]["google_linked"] is True
        assert set(AuditLog.objects.values_list("action", flat=True)) == {
            "USER_REGISTERED",
            "GOOGLE_LINKED",
        }

    def test_existing_email_account_is_linked_not_duplicated(self):
        existing = User.objects.create_user(email="alice@gmail.com")

        first_google_login()

        assert User.objects.count() == 1
        existing.refresh_from_db()
        assert existing.google_id == "google-sub-alice"

    def test_wrong_code_does_not_link(self):
        start(APIClient())
        code = emailed_code()
        response = verify(APIClient(), "000000" if code != "000000" else "111111")

        assert response.status_code == 400
        assert response.json()["error_code"] == "OTP_INVALID"
        assert not User.objects.exists()

    def test_code_is_bound_to_the_google_account_it_was_sent_for(self):
        """An impostor's Google account using the victim's email can't reuse the victim's code."""
        User.objects.create_user(email="alice@gmail.com")
        start(APIClient(), token="tok-alice")
        code = emailed_code()

        response = verify(APIClient(), code, token="tok-impostor")

        assert response.json()["error_code"] == "OTP_INVALID"
        assert User.objects.get().google_id is None

    def test_impostor_without_inbox_access_cannot_take_over(self):
        """The core reason for option C: email match alone never grants access."""
        User.objects.create_user(email="alice@gmail.com")

        response = start(APIClient(), token="tok-impostor")

        assert response.json()["data"]["status"] == "OTP_REQUIRED"
        assert "access" not in response.json()["data"]
        # The code went to the real owner's inbox, not to the impostor.
        assert mail.outbox[-1].to == ["alice@gmail.com"]

    def test_google_link_otp_cannot_be_requested_through_public_endpoint(self):
        response = APIClient().post(
            OTP_REQUEST_URL,
            {
                "channel": "EMAIL",
                "identifier": "alice@gmail.com",
                "purpose": "GOOGLE_LINK",
            },
            format="json",
        )
        assert response.status_code == 400
        assert "purpose" in response.json()["errors"]

    def test_login_otp_cannot_complete_google_link(self):
        User.objects.create_user(email="alice@gmail.com")
        APIClient().post(
            OTP_REQUEST_URL,
            {"channel": "EMAIL", "identifier": "alice@gmail.com", "purpose": "LOGIN"},
            format="json",
        )
        login_code = emailed_code()

        response = verify(APIClient(), login_code)
        assert response.json()["error_code"] == "OTP_INVALID"

    def test_cooldown_applies(self):
        start(APIClient())
        response = start(APIClient())
        assert response.status_code == 429
        assert response.json()["error_code"] == "OTP_COOLDOWN"


@pytest.mark.django_db
class TestLinkedGoogleLogin:
    def test_second_login_is_one_click(self):
        first_google_login()
        mail.outbox.clear()

        response = start(APIClient())

        data = response.json()["data"]
        assert data["status"] == "AUTHENTICATED"
        assert data["access"] and data["refresh"]
        assert mail.outbox == []
        assert UserSession.objects.count() == 2  # two logins, two sessions

    def test_disabled_account_refused(self):
        first_google_login()
        User.objects.update(is_active=False)

        response = start(APIClient())
        assert response.status_code == 403
        assert response.json()["error_code"] == "ACCOUNT_DISABLED"

    def test_soft_deleted_account_refused(self):
        first_google_login()
        User.objects.get().soft_delete()

        assert start(APIClient()).status_code == 403

    def test_account_linked_to_other_google_account_conflicts(self):
        user = User.objects.create_user(email="alice@gmail.com")
        user.google_id = "some-other-google-account"
        user.save()

        start(APIClient())  # alice's real Google account, not yet linked
        response = verify(APIClient(), emailed_code())

        assert response.status_code == 409
        assert response.json()["error_code"] == "GOOGLE_ACCOUNT_CONFLICT"
        user.refresh_from_db()
        assert user.google_id == "some-other-google-account"


@pytest.mark.django_db
class TestTokenChecks:
    def test_invalid_token(self):
        response = start(APIClient(), token="garbage")
        assert response.status_code == 401
        assert response.json()["error_code"] == "GOOGLE_TOKEN_INVALID"

    def test_unverified_google_email_refused(self):
        TOKENS["tok-unverified"] = {**ALICE, "sub": "x", "email_verified": False}
        try:
            response = start(APIClient(), token="tok-unverified")
        finally:
            del TOKENS["tok-unverified"]
        assert response.status_code == 400
        assert response.json()["error_code"] == "GOOGLE_EMAIL_NOT_VERIFIED"

    def test_wrong_issuer_refused(self):
        TOKENS["tok-evil"] = {**ALICE, "iss": "https://evil.example.com"}
        try:
            response = start(APIClient(), token="tok-evil")
        finally:
            del TOKENS["tok-evil"]
        assert response.json()["error_code"] == "GOOGLE_TOKEN_INVALID"

    def test_token_without_email_refused(self):
        TOKENS["tok-noemail"] = {k: v for k, v in ALICE.items() if k != "email"}
        try:
            response = start(APIClient(), token="tok-noemail")
        finally:
            del TOKENS["tok-noemail"]
        assert response.json()["error_code"] == "GOOGLE_TOKEN_INVALID"

    def test_audience_is_our_client_id(self, google, settings):
        start(APIClient())
        assert google.call_args.kwargs["audience"] == settings.GOOGLE_ALLOWED_AUDIENCES

    def test_google_unreachable_is_503(self, google):
        google.side_effect = google_exceptions.TransportError("network down")
        response = start(APIClient())
        assert response.status_code == 503
        assert response.json()["error_code"] == "GOOGLE_UNAVAILABLE"

    def test_not_configured_is_503(self, settings):
        settings.GOOGLE_ALLOWED_AUDIENCES = []
        response = start(APIClient())
        assert response.status_code == 503
        assert response.json()["error_code"] == "GOOGLE_NOT_CONFIGURED"


@pytest.mark.django_db
class TestUnlink:
    def test_unlink_then_next_google_login_needs_otp_again(self):
        tokens = first_google_login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = client.post(UNLINK_URL)

        assert response.status_code == 200
        assert response.json()["data"]["google_linked"] is False
        assert User.objects.get().google_id is None
        assert AuditLog.objects.filter(action="GOOGLE_UNLINKED").exists()
        assert client.get(ME_URL).status_code == 200  # session survives
        assert start(APIClient()).json()["data"]["status"] == "OTP_REQUIRED"

    def test_unlink_when_not_linked(self):
        user = User.objects.create_user(email="bob@example.com")
        from apps.accounts.services.tokens import issue_tokens

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
        response = client.post(UNLINK_URL)
        assert response.status_code == 400
        assert response.json()["error_code"] == "GOOGLE_NOT_LINKED"

    def test_unlink_requires_auth(self):
        assert APIClient().post(UNLINK_URL).status_code == 401
