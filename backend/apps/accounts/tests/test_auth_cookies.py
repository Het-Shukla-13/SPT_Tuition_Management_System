"""
Phase 9: the refresh token lives in an HttpOnly cookie, the way the browser
app will use it (REFRESH_TOKEN_IN_BODY off, as in production).
"""

import re
from unittest import mock

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User

REQUEST_URL = "/api/v1/auth/otp/request/"
VERIFY_URL = "/api/v1/auth/otp/verify/"
REFRESH_URL = "/api/v1/auth/token/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
LOGOUT_ALL_URL = "/api/v1/auth/logout-all/"
GOOGLE_URL = "/api/v1/auth/google/"
ME_URL = "/api/v1/auth/me/"
COOKIE = "tms_refresh"
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def browser_mode(settings):
    settings.REFRESH_TOKEN_IN_BODY = False
    cache.clear()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="parent@example.com")


def login(client: APIClient):
    body = {"channel": "EMAIL", "identifier": "parent@example.com", "purpose": "LOGIN"}
    assert client.post(REQUEST_URL, body, format="json").status_code == 200
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    response = client.post(VERIFY_URL, {**body, "code": code}, format="json")
    assert response.status_code == 200, response.json()
    return response


def refresh(client: APIClient, **headers):
    return client.post(REFRESH_URL, {}, format="json", **headers)


class TestLoginSetsCookie:
    def test_refresh_token_only_in_httponly_cookie(self, user):
        response = login(APIClient())
        data = response.json()["data"]
        assert "access" in data and "refresh" not in data

        cookie = response.cookies[COOKIE]
        assert cookie.value
        assert cookie["httponly"] is True
        assert cookie["secure"] is True
        assert cookie["samesite"] == "Lax"
        assert cookie["path"] == "/api/v1/auth/"  # never sent with other API calls
        assert int(cookie["max-age"]) == 7 * 24 * 3600

    def test_google_one_click_login_sets_cookie_too(self, user):
        user.google_id = "sub-1"
        user.save()
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "sub-1",
            "email": "parent@example.com",
            "email_verified": True,
        }
        with mock.patch(
            "google.oauth2.id_token.verify_oauth2_token", return_value=claims
        ):
            response = APIClient().post(GOOGLE_URL, {"id_token": "t"}, format="json")
        assert response.json()["data"]["status"] == "AUTHENTICATED"
        assert response.cookies[COOKIE].value
        assert "refresh" not in response.json()["data"]


class TestRefreshWithCookie:
    def test_page_reload_gets_new_access_and_rotated_cookie(self, user):
        client = APIClient()  # keeps cookies between requests, like a browser
        first = login(client).cookies[COOKIE].value

        response = refresh(client, **XHR)

        assert response.status_code == 200, response.json()
        access = response.json()["data"]["access"]
        assert response.cookies[COOKIE].value not in ("", first)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert client.get(ME_URL).status_code == 200

    def test_cookie_without_csrf_header_rejected(self, user):
        client = APIClient()
        login(client)
        response = refresh(client)
        assert response.status_code == 403
        assert response.json()["error_code"] == "CSRF_HEADER_MISSING"

    def test_no_cookie_no_body_means_log_in(self, db):
        response = refresh(APIClient(), **XHR)
        assert response.status_code == 401

    def test_dead_cookie_is_cleared(self, user):
        client = APIClient()
        login(client)
        client.cookies[COOKIE] = "not-a-real-token"
        response = refresh(client, **XHR)
        assert response.status_code == 401
        assert response.cookies[COOKIE].value == ""
        assert int(response.cookies[COOKIE]["max-age"]) == 0

    def test_body_token_still_accepted_without_header(self, user, settings):
        # Swagger / tests / a future mobile app send the token in the body.
        settings.REFRESH_TOKEN_IN_BODY = True
        raw = login(APIClient()).json()["data"]["refresh"]
        response = APIClient().post(REFRESH_URL, {"refresh": raw}, format="json")
        assert response.status_code == 200


class TestLogoutClearsCookie:
    @pytest.mark.parametrize("url", [LOGOUT_URL, LOGOUT_ALL_URL])
    def test_logout_clears_cookie_and_cookie_stops_working(self, user, url):
        client = APIClient()
        access = login(client).json()["data"]["access"]
        old_cookie = client.cookies[COOKIE].value
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = client.post(url, {}, format="json")

        assert response.status_code == 200
        assert response.cookies[COOKIE].value == ""
        # Even if a copy of the old cookie survived somewhere, the session is over.
        stale = APIClient()
        stale.cookies[COOKIE] = old_cookie
        assert refresh(stale, **XHR).status_code == 401


def test_cors_exposes_request_id_and_download_names(settings):
    assert {"X-Request-ID", "Content-Disposition"} <= set(settings.CORS_EXPOSE_HEADERS)
