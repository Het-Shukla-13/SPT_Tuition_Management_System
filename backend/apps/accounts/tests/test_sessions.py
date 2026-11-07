"""Session-backed JWT tests: multi-device sessions, revocation, rotation races, reuse detection."""

import re
from datetime import timedelta

import jwt
import pytest
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserSession

VERIFY_URL = "/api/v1/auth/otp/verify/"
REQUEST_URL = "/api/v1/auth/otp/request/"
REFRESH_URL = "/api/v1/auth/token/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
LOGOUT_ALL_URL = "/api/v1/auth/logout-all/"
SESSIONS_URL = "/api/v1/auth/sessions/"
ME_URL = "/api/v1/auth/me/"

EMAIL = "student@example.com"


def login(email=EMAIL, user_agent="TestBrowser/1.0", purpose="LOGIN"):
    """Log in from a fresh 'device' and return (client, tokens)."""
    cache.clear()  # skip the OTP resend cooldown between logins
    client = APIClient(HTTP_USER_AGENT=user_agent)
    body = {"channel": "EMAIL", "identifier": email, "purpose": purpose}
    assert client.post(REQUEST_URL, body, format="json").status_code == 200
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    response = client.post(VERIFY_URL, {**body, "code": code}, format="json")
    assert response.status_code == 200, response.json()
    tokens = response.json()["data"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client, tokens


def refresh(raw):
    return APIClient().post(REFRESH_URL, {"refresh": raw}, format="json")


@pytest.fixture
def user(db):
    return User.objects.create_user(email=EMAIL)


@pytest.mark.django_db
class TestSessionLifecycle:
    def test_login_creates_session_and_tokens_carry_sid(self, user):
        _, tokens = login()

        session = UserSession.objects.get(user=user)
        claims = jwt.decode(tokens["access"], options={"verify_signature": False})
        assert claims["sid"] == session.session_id
        assert claims["iss"] == "spt-tms-api"
        assert session.user_agent == "TestBrowser/1.0"
        assert session.ip_address == "127.0.0.1"
        assert session.is_active

    def test_list_sessions_marks_current_device(self, user):
        laptop, _ = login(user_agent="Laptop")
        login(user_agent="Phone")

        response = laptop.get(SESSIONS_URL)

        assert response.status_code == 200
        sessions = response.json()["data"]
        assert len(sessions) == 2
        current = [s for s in sessions if s["is_current"]]
        assert len(current) == 1 and current[0]["user_agent"] == "Laptop"

    def test_list_requires_authentication(self):
        assert APIClient().get(SESSIONS_URL).status_code == 401

    def test_logout_ends_only_this_device(self, user):
        laptop, laptop_tokens = login(user_agent="Laptop")
        phone, _ = login(user_agent="Phone")

        assert laptop.post(LOGOUT_URL, {}, format="json").status_code == 200

        assert laptop.get(ME_URL).status_code == 401
        assert refresh(laptop_tokens["refresh"]).status_code == 401
        assert phone.get(ME_URL).status_code == 200
        assert (
            UserSession.objects.get(revoked_at__isnull=False).revoked_reason == "LOGOUT"
        )

    def test_logout_all_ends_every_device(self, user):
        laptop, laptop_tokens = login(user_agent="Laptop")
        phone, phone_tokens = login(user_agent="Phone")

        response = laptop.post(LOGOUT_ALL_URL, format="json")

        assert response.json()["data"] == {"sessions_ended": 2}
        for client, tokens in [(laptop, laptop_tokens), (phone, phone_tokens)]:
            assert client.get(ME_URL).status_code == 401
            assert refresh(tokens["refresh"]).status_code == 401

    def test_revoke_another_device(self, user):
        laptop, _ = login(user_agent="Laptop")
        phone, _ = login(user_agent="Phone")
        phone_session = UserSession.objects.get(user_agent="Phone")

        response = laptop.delete(f"{SESSIONS_URL}{phone_session.id}/")

        assert response.status_code == 200
        assert phone.get(ME_URL).status_code == 401
        assert laptop.get(ME_URL).status_code == 200

    def test_cannot_revoke_someone_elses_session(self, user):
        User.objects.create_user(email="other@example.com")
        other_client, _ = login(email="other@example.com")
        attacker, _ = login()
        victim_session = UserSession.objects.get(user__email="other@example.com")

        response = attacker.delete(f"{SESSIONS_URL}{victim_session.id}/")

        assert response.status_code == 404
        assert other_client.get(ME_URL).status_code == 200

    def test_revoked_sessions_not_listed(self, user):
        laptop, _ = login(user_agent="Laptop")
        phone, _ = login(user_agent="Phone")
        phone.post(LOGOUT_URL, {}, format="json")

        sessions = laptop.get(SESSIONS_URL).json()["data"]
        assert [s["user_agent"] for s in sessions] == ["Laptop"]


@pytest.mark.django_db
class TestRefreshRotation:
    def test_refresh_slides_session_and_updates_activity(self, user):
        _, tokens = login()
        session = UserSession.objects.get()
        UserSession.objects.filter(pk=session.pk).update(
            last_active_at=timezone.now() - timedelta(hours=1)
        )

        new = refresh(tokens["refresh"]).json()["data"]

        session.refresh_from_db()
        assert session.last_active_at > timezone.now() - timedelta(minutes=1)
        new_claims = jwt.decode(new["refresh"], options={"verify_signature": False})
        assert session.refresh_token_jti == new_claims["jti"]
        assert new_claims["sid"] == session.session_id  # same login

    def test_concurrent_refresh_within_grace_gets_same_pair(self, user):
        _, tokens = login()

        first = refresh(tokens["refresh"])
        second = refresh(tokens["refresh"])  # e.g. a second tab

        assert first.status_code == second.status_code == 200
        assert first.json()["data"] == second.json()["data"]
        assert UserSession.objects.get().is_active

    def test_reuse_after_grace_window_revokes_whole_session(self, user):
        client, tokens = login()
        rotated = refresh(tokens["refresh"]).json()["data"]
        cache.clear()  # grace window over

        stolen = refresh(tokens["refresh"])

        assert stolen.status_code == 401
        session = UserSession.objects.get()
        assert session.revoked_reason == "REFRESH_REUSE"
        # The legitimate holder is logged out too: the thief's copy dies with it.
        assert refresh(rotated["refresh"]).status_code == 401
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {rotated['access']}")
        assert client.get(ME_URL).status_code == 401

    def test_max_session_lifetime_enforced(self, user):
        _, tokens = login()
        UserSession.objects.update(
            created_at=timezone.now()
            - timedelta(days=settings.SESSION_MAX_LIFETIME_DAYS + 1)
        )

        response = refresh(tokens["refresh"])

        assert response.status_code == 401
        assert response.json()["error_code"] == "SESSION_EXPIRED"
        assert UserSession.objects.get().revoked_reason == "LIFETIME_EXCEEDED"

    def test_access_token_cannot_be_used_as_refresh(self, user):
        _, tokens = login()
        assert refresh(tokens["access"]).status_code == 401

    def test_garbage_refresh_token(self):
        response = refresh("not-a-token")
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_NOT_VALID"

    def test_refresh_requires_field(self):
        response = APIClient().post(REFRESH_URL, {}, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestTokenValidation:
    def test_token_without_sid_rejected(self, user):
        # A token minted outside the session flow (no sid claim).
        access = RefreshToken.for_user(user).access_token
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = client.get(ME_URL)
        assert response.status_code == 401
        assert response.json()["message"] == "Please log in again."

    def test_token_from_another_issuer_rejected(self, user):
        _, tokens = login()
        claims = jwt.decode(tokens["access"], options={"verify_signature": False})
        claims["iss"] = "some-other-system"
        forged = jwt.encode(
            claims, settings.SIMPLE_JWT["SIGNING_KEY"], algorithm="HS256"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {forged}")
        assert client.get(ME_URL).status_code == 401

    def test_token_signed_with_wrong_key_rejected(self, user):
        _, tokens = login()
        claims = jwt.decode(tokens["access"], options={"verify_signature": False})
        forged = jwt.encode(claims, "attacker-key-" * 4, algorithm="HS256")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {forged}")
        assert client.get(ME_URL).status_code == 401

    def test_role_claim_is_never_trusted(self, user):
        """Even a validly-signed token claiming ADMIN changes nothing: role comes from the DB."""
        _, tokens = login()
        claims = jwt.decode(tokens["access"], options={"verify_signature": False})
        claims["role"] = "ADMIN"
        forged = jwt.encode(
            claims, settings.SIMPLE_JWT["SIGNING_KEY"], algorithm="HS256"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {forged}")
        response = client.get(ME_URL)

        assert response.status_code == 200
        assert response.json()["data"]["role"] == "PORTAL"
        assert not User.objects.get(pk=user.pk).is_admin
