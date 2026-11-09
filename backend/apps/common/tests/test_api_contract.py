"""
Phase 9 contract guards: what the frontend can rely on for EVERY endpoint.

- Every JSON answer under /api/ is the envelope
  {success, message, data, errors, error_code, meta}, for every role and
  method, including errors raised outside DRF (unknown URL, bad Host).
- Lists are paginated with the standard `meta`, except the few small
  per-user lists named below.
New endpoints are covered automatically (the URL conf is walked).
"""

import json

import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.common.error_views import server_error
from apps.common.tests.test_security_audit import ENDPOINTS

ENVELOPE = {"success", "message", "data", "errors", "error_code", "meta"}
PAGE_META = {
    "page",
    "page_size",
    "total_count",
    "total_pages",
    "has_next",
    "has_previous",
}
METHODS = ["get", "post", "put", "patch", "delete"]

# Small, bounded lists returned whole (meta is null): a user's own sessions,
# one student's fee accounts, a parent's children.
UNPAGINATED_LISTS = {
    "/api/v1/auth/sessions/",
    "/api/v1/admin/fees/students/1/accounts/",
    "/api/v1/portal/students/",
}


def _client(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


@pytest.fixture
def clients(db):
    admin = User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)
    teacher = User.objects.create_user(email="t@example.com", role=User.Role.TEACHER)
    portal = User.objects.create_user(email="p@example.com")
    return {
        "anonymous": _client(),
        "admin": _client(admin),
        "teacher": _client(teacher),
        "portal": _client(portal),
    }


def _assert_envelope(response, label):
    content_type = response.get("Content-Type", "")
    assert "application/json" in content_type, f"{label}: {content_type}"
    body = response.json()
    assert isinstance(body, dict) and set(body) == ENVELOPE, f"{label}: {body}"
    assert body["success"] is (response.status_code < 400), label
    if not body["success"]:
        assert body["error_code"], f"{label}: error without error_code"


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["anonymous", "admin", "teacher", "portal"])
def test_every_endpoint_answers_with_the_envelope(clients, role):
    client = clients[role]
    for name, path in ENDPOINTS:
        for method in METHODS:
            response = getattr(client, method)(path, {}, format="json")
            if response.status_code == 405:
                _assert_envelope(response, f"{role} {method} {path}")
                continue
            if "json" not in response.get("Content-Type", ""):
                # File downloads (PDF/photo) legitimately aren't JSON; with an
                # empty database they can't succeed, so this means a bug.
                pytest.fail(f"{role} {method} {path} ({name}): non-JSON answer")
            _assert_envelope(response, f"{role} {method} {path} ({name})")


@pytest.mark.django_db
def test_lists_are_paginated(clients):
    admin, portal = clients["admin"], clients["portal"]
    for _, path in ENDPOINTS:
        client = portal if path.startswith("/api/v1/portal/") else admin
        response = client.get(path)
        if response.status_code != 200 or not isinstance(response.json()["data"], list):
            continue
        meta = response.json()["meta"]
        if path in UNPAGINATED_LISTS:
            assert meta is None, path
        else:
            assert meta is not None and set(meta) == PAGE_META, f"{path}: {meta}"


class TestErrorsOutsideViews:
    def test_unknown_api_url(self, db):
        response = APIClient().get("/api/v1/does-not-exist/")
        assert response.status_code == 404
        _assert_envelope(response, "unknown url")
        assert response.json()["error_code"] == "NOT_FOUND"
        assert response["X-Request-ID"]  # still traceable

    def test_bad_host_header(self, db):
        response = APIClient(HTTP_HOST="evil.example").get("/api/v1/health/")
        assert response.status_code == 400
        _assert_envelope(response, "bad host")

    def test_crash_outside_a_view(self):
        response = server_error(RequestFactory().get("/api/v1/anything/"))
        assert response.status_code == 500
        assert json.loads(response.content)["error_code"] == "INTERNAL_ERROR"

    def test_non_api_pages_keep_django_html(self, db):
        response = APIClient().get("/not-an-api-page/")
        assert response.status_code == 404
        assert "text/html" in response["Content-Type"]
