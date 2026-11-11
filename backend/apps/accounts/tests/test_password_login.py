"""
Phase 1.5: email + password login, an emailed code on every new device,
first/forgot password, change password, trusted devices.
Rules: docs/plans/phase-1-5-password-login.md.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import OTPChallenge, TrustedDevice, User, UserSession
from apps.accounts.services.tokens import issue_tokens
from apps.accounts.tests.helpers import (
    PASSWORD,
    last_emailed_code,
    make_user,
    password_login,
)

LOGIN = "/api/v1/auth/login/"
VERIFY = "/api/v1/auth/login/verify/"
RESEND = "/api/v1/auth/login/resend/"
RESET = "/api/v1/auth/password/reset/"
RESET_CONFIRM = "/api/v1/auth/password/reset/confirm/"
CHANGE = "/api/v1/auth/password/change/"
DEVICES = "/api/v1/auth/devices/"
LOGOUT_ALL = "/api/v1/auth/logout-all/"
ME = "/api/v1/auth/me/"
EMAIL = "kavita@example.com"
NEW_PASSWORD = "Sai-Tuitions-Rocks-42"


def post(client, url, body):
    return client.post(url, body, format="json")


def login(client, email=EMAIL, password=PASSWORD):
    return post(client, LOGIN, {"email": email, "password": password})


def bearer(client, response):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['data']['access']}")
    return client


@pytest.fixture
def user(db):
    return make_user(EMAIL, first_name="Kavita", last_name="Shah")


# ── new device vs trusted device ─────────────────────────────
@pytest.mark.django_db
class TestNewDevice:
    def test_first_login_on_a_device_needs_the_emailed_code(self, user):
        browser = APIClient()
        response = login(browser)

        data = response.json()["data"]
        assert data["status"] == "OTP_REQUIRED"
        assert data["email"] == "k****a@example.com"
        assert data["login_ticket"] and "access" not in data
        assert mail.outbox[-1].to == [EMAIL]
        assert "new device sign-in" in mail.outbox[-1].subject

        response = post(
            browser,
            VERIFY,
            {"login_ticket": data["login_ticket"], "code": last_emailed_code()},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "AUTHENTICATED"
        cookie = response.cookies["tms_device"]
        assert cookie["httponly"] and cookie["path"] == "/api/v1/auth/"
        assert int(cookie["max-age"]) == 90 * 24 * 3600
        device = TrustedDevice.objects.get()
        assert device.token_hash != cookie.value  # only the hash is stored

    def test_trusted_device_logs_in_with_password_only(self, user):
        browser = APIClient()
        password_login(browser, EMAIL)
        mail.outbox.clear()

        response = login(browser)
        assert response.json()["data"]["status"] == "AUTHENTICATED"
        assert mail.outbox == []

    def test_another_device_still_needs_a_code(self, user):
        password_login(APIClient(), EMAIL)
        cache.clear()  # a minute later
        assert login(APIClient()).json()["data"]["status"] == "OTP_REQUIRED"

    def test_second_new_device_within_a_minute_is_asked_to_wait(self, user):
        # Anti-flooding: one new-device email per minute; the app shows a countdown.
        password_login(APIClient(), EMAIL)
        response = login(APIClient())
        assert response.status_code == 429
        assert response.json()["error_code"] == "OTP_COOLDOWN"
        assert response.json()["errors"]["retry_after_seconds"] > 0

    def test_trust_expires_after_90_days(self, user):
        browser = APIClient()
        password_login(browser, EMAIL)
        TrustedDevice.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        cache.clear()
        assert login(browser).json()["data"]["status"] == "OTP_REQUIRED"

    def test_one_browser_trusted_by_two_family_members(self, user):
        make_user("arav@example.com")
        laptop = APIClient()
        password_login(laptop, EMAIL)
        password_login(laptop, "arav@example.com")
        assert TrustedDevice.objects.count() == 2
        cache.clear()
        assert login(laptop).json()["data"]["status"] == "AUTHENTICATED"
        assert (
            login(laptop, "arav@example.com").json()["data"]["status"]
            == "AUTHENTICATED"
        )

    def test_logging_out_keeps_the_device_trusted(self, user):
        browser = APIClient()
        bearer(browser, password_login(browser, EMAIL))
        post(browser, "/api/v1/auth/logout/", {})
        browser.credentials()
        cache.clear()
        assert login(browser).json()["data"]["status"] == "AUTHENTICATED"


# ── the login ticket: a code alone isn't enough ──────────────
@pytest.mark.django_db
class TestLoginTicket:
    def test_someone_reading_the_inbox_cannot_use_the_code_without_the_ticket(
        self, user
    ):
        login(APIClient())  # the real user, on their own new phone
        code = last_emailed_code()

        attacker = APIClient()  # knows the code (inbox) but never typed the password
        forged = post(
            attacker, VERIFY, {"login_ticket": "forged.ticket.value", "code": code}
        )
        assert forged.json()["error_code"] == "LOGIN_TICKET_INVALID"

    def test_another_users_ticket_does_not_fit_this_code(self, user):
        make_user("other@example.com")
        login(APIClient())
        code = last_emailed_code()
        other_ticket = login(APIClient(), "other@example.com").json()["data"][
            "login_ticket"
        ]

        response = post(
            APIClient(), VERIFY, {"login_ticket": other_ticket, "code": code}
        )
        assert response.json()["error_code"] in {"OTP_INVALID", "LOGIN_TICKET_INVALID"}
        assert not UserSession.objects.filter(user__email="other@example.com").exists()

    def test_logging_in_again_quickly_moves_the_code_to_the_new_ticket(self, user):
        first_ticket = login(APIClient()).json()["data"]["login_ticket"]
        code = last_emailed_code()
        second_ticket = login(APIClient()).json()["data"][
            "login_ticket"
        ]  # page reloaded
        assert len(mail.outbox) == 1  # no second email inside the cooldown

        assert (
            post(
                APIClient(), VERIFY, {"login_ticket": first_ticket, "code": code}
            ).json()["error_code"]
            == "OTP_INVALID"
        )
        assert (
            post(
                APIClient(), VERIFY, {"login_ticket": second_ticket, "code": code}
            ).status_code
            == 200
        )

    def test_resend_replaces_the_code(self, user):
        ticket = login(APIClient()).json()["data"]["login_ticket"]
        old_code = last_emailed_code()
        cache.clear()  # past the resend cooldown

        assert post(APIClient(), RESEND, {"login_ticket": ticket}).status_code == 200
        new_code = last_emailed_code()
        if new_code != old_code:
            assert (
                post(
                    APIClient(), VERIFY, {"login_ticket": ticket, "code": old_code}
                ).json()["error_code"]
                == "OTP_INVALID"
            )
        assert (
            post(
                APIClient(), VERIFY, {"login_ticket": ticket, "code": new_code}
            ).status_code
            == 200
        )

    def test_expired_ticket(self, user, settings):
        ticket = login(APIClient()).json()["data"]["login_ticket"]
        settings.LOGIN_TICKET_MAX_AGE_SECONDS = -1
        response = post(
            APIClient(), VERIFY, {"login_ticket": ticket, "code": last_emailed_code()}
        )
        assert response.json()["error_code"] == "LOGIN_TICKET_INVALID"


# ── wrong passwords ──────────────────────────────────────────
@pytest.mark.django_db
class TestWrongPassword:
    @pytest.mark.parametrize(
        "email,password",
        [
            (EMAIL, "wrong-password"),
            ("nobody@example.com", PASSWORD),
            ("nopassword@example.com", PASSWORD),
            ("deleted@example.com", PASSWORD),
        ],
    )
    def test_every_failure_looks_the_same(self, user, email, password):
        make_user("nopassword@example.com", password=None)
        make_user("deleted@example.com").soft_delete()

        response = login(APIClient(), email, password)
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_CREDENTIALS"
        assert mail.outbox == []

    def test_five_wrong_passwords_lock_even_the_right_one(self, user):
        for _ in range(5):
            login(APIClient(), password="nope-nope-nope")
        response = login(APIClient())
        assert response.status_code == 429
        assert response.json()["error_code"] == "LOGIN_LOCKED"
        assert 0 < response.json()["errors"]["retry_after_seconds"] <= 900

    def test_unknown_emails_lock_the_same_way(self, db):
        # Otherwise "locked" vs "wrong password" would reveal which emails exist.
        for _ in range(5):
            login(APIClient(), "nobody@example.com", "x" * 10)
        assert (
            login(APIClient(), "nobody@example.com", "x" * 10).json()["error_code"]
            == "LOGIN_LOCKED"
        )

    def test_success_resets_the_counter(self, user):
        for _ in range(4):
            login(APIClient(), password="nope-nope-nope")
        assert login(APIClient()).status_code == 200
        for _ in range(4):
            login(APIClient(), password="nope-nope-nope")
        assert login(APIClient()).json()["error_code"] != "LOGIN_LOCKED"

    def test_disabled_account_with_right_password(self, user):
        User.objects.filter(pk=user.pk).update(is_active=False)
        response = login(APIClient())
        assert response.status_code == 403
        assert response.json()["error_code"] == "ACCOUNT_DISABLED"

    def test_email_is_matched_case_insensitively(self, user):
        assert login(APIClient(), "  Kavita@Example.COM ").status_code == 200


# ── first password / forgot password ─────────────────────────
@pytest.mark.django_db
class TestSetOrResetPassword:
    def test_invited_user_sets_first_password_and_is_logged_in(self, db):
        invited = make_user(EMAIL, password=None)
        browser = APIClient()

        assert post(browser, RESET, {"email": EMAIL}).status_code == 200
        response = post(
            browser,
            RESET_CONFIRM,
            {"email": EMAIL, "code": last_emailed_code(), "new_password": NEW_PASSWORD},
        )

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "AUTHENTICATED"
        assert response.cookies["tms_device"].value
        invited.refresh_from_db()
        assert invited.check_password(NEW_PASSWORD)
        assert (
            invited.activated_at is not None and invited.email_verified_at is not None
        )
        cache.clear()
        assert (
            login(browser, password=NEW_PASSWORD).json()["data"]["status"]
            == "AUTHENTICATED"
        )

    def test_unknown_email_gets_the_same_answer_and_nothing_is_sent(self, db):
        response = post(APIClient(), RESET, {"email": "nobody@example.com"})
        assert response.status_code == 200
        assert (
            response.json()["message"]
            == "If this email has an account, we've sent a code to it."
        )
        assert mail.outbox == []

    def test_weak_password_rejected_without_using_up_the_code(self, user):
        post(APIClient(), RESET, {"email": EMAIL})
        code = last_emailed_code()

        weak = post(
            APIClient(),
            RESET_CONFIRM,
            {"email": EMAIL, "code": code, "new_password": "12345678"},
        )
        assert weak.status_code == 400
        assert "new_password" in weak.json()["errors"]

        ok = post(
            APIClient(),
            RESET_CONFIRM,
            {"email": EMAIL, "code": code, "new_password": NEW_PASSWORD},
        )
        assert ok.status_code == 200

    def test_reset_ends_every_other_session_and_device(self, user):
        old_phone = APIClient()
        bearer(old_phone, password_login(old_phone, EMAIL))

        post(APIClient(), RESET, {"email": EMAIL})
        post(
            APIClient(),
            RESET_CONFIRM,
            {"email": EMAIL, "code": last_emailed_code(), "new_password": NEW_PASSWORD},
        )

        assert old_phone.get(ME).status_code == 401
        assert TrustedDevice.objects.active().count() == 1  # only the resetting browser
        user.refresh_from_db()
        assert not user.check_password(PASSWORD)

    def test_wrong_code(self, user):
        post(APIClient(), RESET, {"email": EMAIL})
        response = post(
            APIClient(),
            RESET_CONFIRM,
            {"email": EMAIL, "code": "000000", "new_password": NEW_PASSWORD},
        )
        if response.status_code != 200:  # 1-in-a-million: the real code was 000000
            assert response.json()["error_code"] == "OTP_INVALID"


# ── change password (logged in) ──────────────────────────────
@pytest.mark.django_db
class TestChangePassword:
    def test_other_devices_logged_out_and_untrusted_this_one_kept(self, user):
        laptop, phone = APIClient(), APIClient()
        bearer(laptop, password_login(laptop, EMAIL))
        bearer(phone, password_login(phone, EMAIL))

        response = post(
            laptop, CHANGE, {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
        )

        assert response.status_code == 200
        assert laptop.get(ME).status_code == 200
        assert phone.get(ME).status_code == 401
        phone.credentials()
        laptop.credentials()
        cache.clear()
        assert (
            login(laptop, password=NEW_PASSWORD).json()["data"]["status"]
            == "AUTHENTICATED"
        )
        assert (
            login(phone, password=NEW_PASSWORD).json()["data"]["status"]
            == "OTP_REQUIRED"
        )

    def test_wrong_current_password(self, user):
        browser = APIClient()
        bearer(browser, password_login(browser, EMAIL))
        response = post(
            browser,
            CHANGE,
            {"current_password": "nope-nope", "new_password": NEW_PASSWORD},
        )
        assert response.json()["error_code"] == "WRONG_PASSWORD"

    def test_weak_new_password(self, user):
        browser = APIClient()
        bearer(browser, password_login(browser, EMAIL))
        response = post(
            browser, CHANGE, {"current_password": PASSWORD, "new_password": "password"}
        )
        assert "new_password" in response.json()["errors"]

    def test_google_only_user_is_told_to_set_a_password(self, db):
        google_user = make_user("g@example.com", password=None)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {issue_tokens(google_user)['access']}"
        )
        response = post(
            client, CHANGE, {"current_password": "x", "new_password": NEW_PASSWORD}
        )
        assert response.json()["error_code"] == "WRONG_PASSWORD"
        assert "Set or reset password" in response.json()["message"]


# ── trusted devices list ─────────────────────────────────────
@pytest.mark.django_db
class TestTrustedDevices:
    def test_list_marks_this_device_and_remove_requires_code_again(self, user):
        laptop = APIClient(HTTP_USER_AGENT="Laptop")
        phone = APIClient(HTTP_USER_AGENT="Phone")
        password_login(phone, EMAIL)
        bearer(laptop, password_login(laptop, EMAIL))

        devices = laptop.get(DEVICES).json()["data"]
        assert {d["label"]: d["is_current"] for d in devices} == {
            "Laptop": True,
            "Phone": False,
        }

        phone_id = next(d["id"] for d in devices if d["label"] == "Phone")
        assert laptop.delete(f"{DEVICES}{phone_id}/").status_code == 200
        cache.clear()
        assert login(phone).json()["data"]["status"] == "OTP_REQUIRED"

    def test_cannot_remove_someone_elses_device(self, user):
        make_user("other@example.com")
        password_login(APIClient(), "other@example.com")
        their_device = TrustedDevice.objects.get(user__email="other@example.com")

        me = APIClient()
        bearer(me, password_login(me, EMAIL))
        assert me.delete(f"{DEVICES}{their_device.pk}/").status_code == 404

    def test_logout_all_untrusts_every_device(self, user):
        browser = APIClient()
        bearer(browser, password_login(browser, EMAIL))
        response = post(browser, LOGOUT_ALL, {})
        assert response.cookies["tms_device"].value == ""
        assert TrustedDevice.objects.active().count() == 0

    def test_deactivation_untrusts_devices(self, user):
        password_login(APIClient(), EMAIL)
        admin = make_user("admin@example.com", role=User.Role.ADMIN)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(admin)['access']}")
        assert (
            client.post(f"/api/v1/admin/users/{user.pk}/deactivate/").status_code == 200
        )
        assert TrustedDevice.objects.active().count() == 0


@pytest.mark.django_db
def test_codes_are_stored_hashed_and_bound_to_purpose(user):
    login(APIClient())
    challenge = OTPChallenge.objects.get()
    assert challenge.purpose == "NEW_DEVICE"
    assert last_emailed_code() not in challenge.code_hash
