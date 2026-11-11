"""
Test helpers for logging in the way the app really does (Phase 1.5):
email + password, plus the emailed new-device code when the browser isn't
trusted yet.
"""

import re

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User

LOGIN_URL = "/api/v1/auth/login/"
LOGIN_VERIFY_URL = "/api/v1/auth/login/verify/"
PASSWORD = "Chalk-and-board-2026"


def make_user(email: str, password: str | None = PASSWORD, **fields) -> User:
    """An invited user who has already set a password (None = no password yet)."""
    return User.objects.create_user(email=email, password=password, **fields)


def last_emailed_code() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def password_login(client: APIClient, email: str, password: str = PASSWORD):
    """
    Log `client` in (it keeps cookies, like a browser): password, then the
    emailed code if this "device" isn't trusted. Returns the final response.
    """
    cache.clear()  # independent of earlier resend cooldowns in the same test
    response = client.post(
        LOGIN_URL, {"email": email, "password": password}, format="json"
    )
    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    if data["status"] == "OTP_REQUIRED":
        response = client.post(
            LOGIN_VERIFY_URL,
            {"login_ticket": data["login_ticket"], "code": last_emailed_code()},
            format="json",
        )
        assert response.status_code == 200, response.json()
    return response
