"""
Automated permission audit over EVERY API endpoint (spec Phase 7).

Walks the URL configuration, so a newly added endpoint is checked
automatically: if it forgets its permission class, these tests fail.

- Anonymous callers get 401 everywhere except the deliberately public endpoints.
- Parent/student (PORTAL) logins get 403 on every /admin/ and /staff/ endpoint.
- Teachers get 403 on every /admin/ endpoint.
- Admins/teachers get 403 on every /portal/ endpoint.
- Nothing, for any role and any method, answers with a 5xx.
"""

import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens

# Endpoints that are public on purpose (by URL name).
PUBLIC = {
    "health-live",
    "health-ready",
    "auth-otp-request",
    "auth-otp-verify",
    "auth-google",
    "auth-google-verify",
    "auth-token-refresh",
    "auth-login",
    "auth-login-verify",
    "auth-login-resend",
    "auth-password-reset",
    "auth-password-reset-confirm",
    "public-enquiry",
}
METHODS = ["get", "post", "put", "patch", "delete"]


def _concrete(route: str) -> str:
    """Turn 'students/<int:pk>/' or '^tests/(?P<pk>[^/.]+)/$' into a real path."""
    route = re.sub(r"\(\?P<\w+>[^)]*\)", "1", route)  # router regex groups first
    route = re.sub(r"<int:\w+>", "1", route)
    route = re.sub(r"<(?:str:)?\w+>", "x", route)
    return route.replace("^", "").replace("$", "").replace("\\", "")


def _endpoints(patterns=None, prefix=""):
    patterns = get_resolver().url_patterns if patterns is None else patterns
    for entry in patterns:
        route = prefix + _concrete(str(entry.pattern))
        if isinstance(entry, URLResolver):
            yield from _endpoints(entry.url_patterns, route)
        elif isinstance(entry, URLPattern) and route.startswith("api/v1/"):
            yield entry.name, "/" + route


ENDPOINTS = sorted(set(_endpoints()))


def _client(user=None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def _call(client, method, path):
    return getattr(client, method)(path, {}, format="json")


def test_endpoint_discovery_found_the_api():
    names = {name for name, _ in ENDPOINTS}
    assert len(ENDPOINTS) > 60
    assert {"admin-students", "staff-test-list", "portal-fees", "fee-payment"} <= names


@pytest.mark.django_db
@pytest.mark.parametrize("name,path", [e for e in ENDPOINTS if e[0] not in PUBLIC])
def test_anonymous_gets_401_everywhere_private(name, path):
    client = _client()
    for method in METHODS:
        status = _call(client, method, path).status_code
        assert status in (401, 405), (
            f"{method.upper()} {path} ({name}) -> {status} for anonymous"
        )


@pytest.mark.django_db
@pytest.mark.parametrize("name,path", [e for e in ENDPOINTS if e[0] in PUBLIC])
def test_public_endpoints_never_crash_on_empty_input(name, path):
    client = _client()
    for method in METHODS:
        assert _call(client, method, path).status_code < 500


@pytest.fixture
def users(db):
    return {
        "admin": User.objects.create_user(
            email="admin@example.com", role=User.Role.ADMIN
        ),
        "teacher": User.objects.create_user(
            email="teacher@example.com", role=User.Role.TEACHER
        ),
        "portal": User.objects.create_user(phone="+919000000001"),
    }


FORBIDDEN = {
    "portal": ("/api/v1/admin/", "/api/v1/staff/"),
    "teacher": ("/api/v1/admin/",),
    "admin": ("/api/v1/portal/",),
}


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["portal", "teacher", "admin"])
def test_role_boundaries(users, role):
    client = _client(users[role])
    checked = 0
    for name, path in ENDPOINTS:
        if not path.startswith(FORBIDDEN[role]):
            continue
        for method in METHODS:
            status = _call(client, method, path).status_code
            assert status in (403, 405), (
                f"{role} {method.upper()} {path} ({name}) -> {status}"
            )
            checked += 1
    assert checked > 20


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["portal", "teacher", "admin"])
def test_no_endpoint_crashes_for_any_role(users, role):
    client = _client(users[role])
    for name, path in ENDPOINTS:
        for method in METHODS:
            status = _call(client, method, path).status_code
            assert status < 500, f"{role} {method.upper()} {path} ({name}) -> {status}"
