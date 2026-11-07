"""
End-to-end tests for OTP registration/login and JWT lifecycle.

Each test name states the behaviour the spec requires (sections 2 and 10.1).
"""

import re
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts.models import OTPChallenge, User
from apps.accounts.services.otp_delivery import OTPDeliveryError
from apps.accounts.services.sms import LocmemSMSBackend
from apps.common.throttling import ResilientScopedRateThrottle

REQUEST_URL = "/api/v1/auth/otp/request/"
VERIFY_URL = "/api/v1/auth/otp/verify/"
REFRESH_URL = "/api/v1/auth/token/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"

EMAIL = "student@example.com"
PHONE = "+919876543210"


# ─── helpers ─────────────────────────────────────────────────
def otp_request(client, identifier=EMAIL, channel="EMAIL", purpose="REGISTER", **extra):
    payload = {
        "channel": channel,
        "identifier": identifier,
        "purpose": purpose,
        **extra,
    }
    return client.post(REQUEST_URL, payload, format="json")


def otp_verify(
    client, code, identifier=EMAIL, channel="EMAIL", purpose="REGISTER", **extra
):
    payload = {
        "channel": channel,
        "identifier": identifier,
        "purpose": purpose,
        "code": code,
        **extra,
    }
    return client.post(VERIFY_URL, payload, format="json")


def code_from_email():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def code_from_sms():
    return re.search(r"\b(\d{6})\b", LocmemSMSBackend.outbox[-1]["message"]).group(1)


def wrong_code(code):
    return "000000" if code != "000000" else "111111"


def register(client, identifier=EMAIL):
    otp_request(client, identifier=identifier)
    response = otp_verify(client, code_from_email(), identifier=identifier)
    assert response.status_code == 200, response.json()
    return response.json()["data"]


def expire_cooldown():
    """Simulate the resend cooldown having passed."""
    from django.core.cache import cache

    cache.clear()


# ─── registration ────────────────────────────────────────────
@pytest.mark.django_db
class TestRegistration:
    def test_email_registration_creates_verified_student_and_returns_tokens(
        self, api_client
    ):
        response = otp_request(api_client)
        assert response.status_code == 200
        assert response.json()["data"] == {
            "expires_in_seconds": 300,
            "resend_after_seconds": 60,
        }
        assert len(mail.outbox) == 1

        response = otp_verify(api_client, code_from_email())

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["access"] and data["refresh"]
        assert data["user"]["email"] == EMAIL
        assert data["user"]["role"] == "STUDENT"
        assert data["user"]["email_verified_at"] is not None
        assert User.objects.filter(email=EMAIL).count() == 1

    def test_phone_registration_normalises_bare_indian_number(self, api_client):
        otp_request(api_client, identifier="98765 43210", channel="PHONE")
        assert LocmemSMSBackend.outbox[-1]["to"] == PHONE

        response = otp_verify(
            api_client, code_from_sms(), identifier="9876543210", channel="PHONE"
        )

        assert response.status_code == 200
        user = User.objects.get(phone=PHONE)
        assert user.phone_verified_at is not None
        assert user.email is None

    def test_email_is_normalised_to_lowercase(self, api_client):
        register(api_client, identifier="  Student@Example.COM ")
        assert User.objects.filter(email=EMAIL).exists()

    def test_role_in_payload_is_ignored(self, api_client):
        otp_request(api_client, role="ADMIN")
        response = otp_verify(api_client, code_from_email(), role="ADMIN")

        assert response.json()["data"]["user"]["role"] == "STUDENT"
        assert not User.objects.filter(role=User.Role.ADMIN).exists()

    def test_register_existing_account_sends_notice_not_otp_with_same_response(
        self, api_client
    ):
        User.objects.create_user(email=EMAIL)

        response = otp_request(api_client)

        assert response.status_code == 200
        assert response.json()["message"] == (
            "If the details are valid, a verification code has been sent."
        )
        assert "already" in mail.outbox[-1].subject.lower()
        assert not re.search(r"\b\d{6}\b", mail.outbox[-1].body)
        assert not OTPChallenge.objects.exists()

    def test_soft_deleted_account_still_blocks_registration(self, api_client):
        User.objects.create_user(email=EMAIL).soft_delete()
        otp_request(api_client)
        assert not OTPChallenge.objects.exists()

    def test_invalid_email_rejected(self, api_client):
        response = otp_request(api_client, identifier="not-an-email")
        assert response.status_code == 400
        assert "identifier" in response.json()["errors"]

    def test_invalid_phone_rejected(self, api_client):
        response = otp_request(api_client, identifier="12345", channel="PHONE")
        assert response.status_code == 400
        assert "identifier" in response.json()["errors"]

    def test_missing_fields_rejected(self, api_client):
        response = api_client.post(REQUEST_URL, {}, format="json")
        assert response.status_code == 400
        assert set(response.json()["errors"]) == {"channel", "identifier", "purpose"}


# ─── login ───────────────────────────────────────────────────
@pytest.mark.django_db
class TestLogin:
    def test_login_existing_user(self, api_client):
        user = User.objects.create_user(email=EMAIL)
        otp_request(api_client, purpose="LOGIN")

        response = otp_verify(api_client, code_from_email(), purpose="LOGIN")

        assert response.status_code == 200
        assert response.json()["data"]["user"]["id"] == user.id
        user.refresh_from_db()
        assert user.last_login is not None
        assert user.email_verified_at is not None

    def test_login_unknown_identity_same_response_nothing_sent(self, api_client):
        response = otp_request(api_client, purpose="LOGIN")

        assert response.status_code == 200
        assert response.json()["message"] == (
            "If the details are valid, a verification code has been sent."
        )
        assert mail.outbox == []
        assert User.objects.count() == 0

    def test_login_otp_cannot_create_an_account(self, api_client):
        otp_request(api_client, purpose="LOGIN")
        response = otp_verify(api_client, "123456", purpose="LOGIN")

        assert response.status_code == 400
        assert response.json()["error_code"] == "OTP_INVALID"
        assert User.objects.count() == 0

    def test_register_otp_cannot_be_used_for_login(self, api_client):
        User.objects.create_user(phone=PHONE)
        otp_request(api_client, identifier=PHONE, channel="PHONE", purpose="LOGIN")
        code = code_from_sms()

        response = otp_verify(
            api_client, code, identifier=PHONE, channel="PHONE", purpose="REGISTER"
        )
        assert response.json()["error_code"] == "OTP_INVALID"

    def test_inactive_user_gets_no_otp(self, api_client):
        User.objects.create_user(email=EMAIL, is_active=False)
        otp_request(api_client, purpose="LOGIN")
        assert mail.outbox == []

    def test_user_disabled_after_otp_sent_is_refused(self, api_client):
        user = User.objects.create_user(email=EMAIL)
        otp_request(api_client, purpose="LOGIN")
        User.objects.filter(pk=user.pk).update(is_active=False)

        response = otp_verify(api_client, code_from_email(), purpose="LOGIN")
        assert response.status_code == 403
        assert response.json()["error_code"] == "ACCOUNT_DISABLED"


# ─── OTP hardening ───────────────────────────────────────────
@pytest.mark.django_db
class TestOTPHardening:
    def test_code_is_stored_hashed(self, api_client):
        otp_request(api_client)
        challenge = OTPChallenge.objects.get()
        assert code_from_email() not in challenge.code_hash

    def test_wrong_code_counts_attempt(self, api_client):
        otp_request(api_client)
        response = otp_verify(api_client, wrong_code(code_from_email()))

        assert response.status_code == 400
        assert response.json()["error_code"] == "OTP_INVALID"
        assert OTPChallenge.objects.get().attempts == 1

    def test_locks_after_max_attempts_even_with_correct_code(self, api_client):
        otp_request(api_client)
        code = code_from_email()
        for _ in range(4):
            otp_verify(api_client, wrong_code(code))

        fifth = otp_verify(api_client, wrong_code(code))
        assert fifth.status_code == 429
        assert fifth.json()["error_code"] == "OTP_ATTEMPTS_EXCEEDED"

        response = otp_verify(api_client, code)
        assert response.json()["error_code"] == "OTP_INVALID"
        assert User.objects.count() == 0

    def test_expired_code_rejected(self, api_client):
        otp_request(api_client)
        OTPChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        response = otp_verify(api_client, code_from_email())
        assert response.json()["error_code"] == "OTP_EXPIRED"

    def test_code_cannot_be_reused(self, api_client):
        otp_request(api_client)
        code = code_from_email()
        assert otp_verify(api_client, code).status_code == 200

        response = otp_verify(api_client, code)
        assert response.json()["error_code"] == "OTP_INVALID"

    def test_new_request_invalidates_previous_code(self, api_client):
        otp_request(api_client)
        first_code = code_from_email()
        expire_cooldown()
        otp_request(api_client)
        second_code = code_from_email()

        if first_code != second_code:
            assert (
                otp_verify(api_client, first_code).json()["error_code"] == "OTP_INVALID"
            )
        assert otp_verify(api_client, second_code).status_code == 200
        assert OTPChallenge.objects.filter(invalidated_at__isnull=False).count() == 1

    def test_resend_within_cooldown_returns_429_with_retry_after(self, api_client):
        otp_request(api_client)
        response = otp_request(api_client)

        assert response.status_code == 429
        body = response.json()
        assert body["error_code"] == "OTP_COOLDOWN"
        assert 0 < body["errors"]["retry_after_seconds"] <= 60
        assert int(response["Retry-After"]) > 0
        assert len(mail.outbox) == 1

    def test_cooldown_applies_even_when_no_account_exists(self, api_client):
        # Otherwise the cooldown itself would reveal whether an account exists.
        otp_request(api_client, purpose="LOGIN")
        assert otp_request(api_client, purpose="LOGIN").status_code == 429

    def test_hourly_cap_per_identifier(self, api_client, settings):
        settings.OTP_RESEND_COOLDOWN_SECONDS = 0
        settings.OTP_MAX_REQUESTS_PER_HOUR = 2
        assert otp_request(api_client).status_code == 200
        assert otp_request(api_client).status_code == 200

        response = otp_request(api_client)
        assert response.status_code == 429
        assert response.json()["error_code"] == "OTP_REQUEST_LIMIT_REACHED"

    def test_per_ip_throttle(self, api_client):
        rates = {"otp_request": "2/hour", "otp_verify": "60/hour"}
        with mock.patch.object(ResilientScopedRateThrottle, "THROTTLE_RATES", rates):
            otp_request(api_client, identifier="a@example.com")
            otp_request(api_client, identifier="b@example.com")
            response = otp_request(api_client, identifier="c@example.com")

        assert response.status_code == 429
        assert response.json()["error_code"] == "THROTTLED"

    def test_delivery_failure_is_reported_and_otp_discarded(self, api_client):
        with mock.patch(
            "apps.accounts.services.otp.deliver_otp", side_effect=OTPDeliveryError
        ):
            response = otp_request(api_client)

        assert response.status_code == 503
        assert response.json()["error_code"] == "OTP_DELIVERY_FAILED"
        assert OTPChallenge.objects.get().invalidated_at is not None

    def test_rate_limit_store_down_fails_closed(self, api_client):
        broken = mock.Mock()
        broken.add.side_effect = ConnectionError("cache down")
        with mock.patch("apps.accounts.services.otp_rate_limit.cache", broken):
            response = otp_request(api_client)

        assert response.status_code == 503
        assert response.json()["error_code"] == "OTP_TEMPORARILY_UNAVAILABLE"
        assert mail.outbox == []

    def test_throttle_store_down_fails_closed_with_503(self, api_client):
        broken = mock.Mock()
        broken.get.side_effect = ConnectionError("cache down")
        with mock.patch.object(ResilientScopedRateThrottle, "cache", broken):
            response = otp_request(api_client)

        assert response.status_code == 503
        assert response.json()["error_code"] == "THROTTLE_UNAVAILABLE"
        assert response["Retry-After"] == "30"

    def test_code_must_be_six_digits(self, api_client):
        response = otp_verify(api_client, "12ab")
        assert response.status_code == 400
        assert "code" in response.json()["errors"]


# ─── JWT lifecycle ───────────────────────────────────────────
@pytest.mark.django_db
class TestTokens:
    def test_me_requires_authentication(self, api_client):
        response = api_client.get(ME_URL)
        assert response.status_code == 401
        assert response.json()["error_code"] == "NOT_AUTHENTICATED"

    def test_me_with_access_token(self, api_client):
        tokens = register(api_client)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = api_client.get(ME_URL)
        assert response.status_code == 200
        assert response.json()["data"]["email"] == EMAIL

    def test_garbage_token_rejected(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not.a.jwt")
        response = api_client.get(ME_URL)
        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_refresh_rotates_the_refresh_token(self, api_client):
        tokens = register(api_client)

        response = api_client.post(
            REFRESH_URL, {"refresh": tokens["refresh"]}, format="json"
        )
        assert response.status_code == 200
        new = response.json()["data"]
        assert new["access"] and new["refresh"] != tokens["refresh"]
        # Reuse of the old token (grace window and reuse detection) is covered
        # in test_sessions.py.

    def test_logout_blacklists_refresh_token(self, api_client):
        tokens = register(api_client)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        assert (
            api_client.post(
                LOGOUT_URL, {"refresh": tokens["refresh"]}, format="json"
            ).status_code
            == 200
        )

        api_client.credentials()
        response = api_client.post(
            REFRESH_URL, {"refresh": tokens["refresh"]}, format="json"
        )
        assert response.status_code == 401

    def test_access_token_dies_immediately_on_logout(self, api_client):
        tokens = register(api_client)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        api_client.post(LOGOUT_URL, {}, format="json")

        response = api_client.get(ME_URL)
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_NOT_VALID"

    def test_cannot_revoke_someone_elses_refresh_token(self, api_client):
        victim = register(api_client, identifier="victim@example.com")
        attacker = register(api_client, identifier="attacker@example.com")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {attacker['access']}")

        response = api_client.post(
            LOGOUT_URL, {"refresh": victim["refresh"]}, format="json"
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_REFRESH_TOKEN"

    def test_soft_deleted_user_tokens_stop_working(self, api_client):
        tokens = register(api_client)
        User.objects.get(email=EMAIL).soft_delete()

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        assert api_client.get(ME_URL).status_code == 401

        api_client.credentials()
        response = api_client.post(
            REFRESH_URL, {"refresh": tokens["refresh"]}, format="json"
        )
        assert response.status_code == 401  # not a 500

    def test_access_token_carries_role_claim(self, api_client):
        import jwt

        tokens = register(api_client)
        claims = jwt.decode(tokens["access"], options={"verify_signature": False})
        assert claims["role"] == "STUDENT"
        assert (
            claims["user_id"] == str(User.objects.get(email=EMAIL).id)
            or claims["user_id"] == User.objects.get(email=EMAIL).id
        )
