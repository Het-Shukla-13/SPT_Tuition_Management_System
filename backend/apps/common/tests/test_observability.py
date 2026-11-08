import json
import logging

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.common.log_formatters import JsonFormatter


@pytest.mark.django_db
class TestRequestLogging:
    def test_logs_method_path_status_user_but_never_query_strings(self, caplog):
        user = User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
        with caplog.at_level(logging.INFO, logger="apps.requests"):
            client.get("/api/v1/admin/users/?search=secret-term")

        record = next(r for r in caplog.records if r.name == "apps.requests")
        assert record.path == "/api/v1/admin/users/"
        assert record.status == 200 and record.user_id == user.pk
        assert "secret-term" not in record.getMessage()

    def test_errors_are_warnings_and_health_is_quiet(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="apps.requests"):
            APIClient().get("/api/v1/admin/users/")
            APIClient().get("/api/v1/health/")
        levels = {
            r.path: r.levelname for r in caplog.records if r.name == "apps.requests"
        }
        assert levels["/api/v1/admin/users/"] == "WARNING"  # 401
        assert levels["/api/v1/health/"] == "DEBUG"

    def test_slow_requests_flagged(self, caplog, settings):
        settings.SLOW_REQUEST_MS = 0
        with caplog.at_level(logging.INFO, logger="apps.requests"):
            APIClient().get("/api/v1/health/")
        assert any(
            r.getMessage().startswith("SLOW ")
            for r in caplog.records
            if r.name == "apps.requests"
        )


@pytest.mark.django_db
class TestSecurityHeaders:
    def test_api_json_responses_are_locked_down(self):
        response = APIClient().get("/api/v1/health/")
        assert (
            response["Content-Security-Policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )
        assert "camera=()" in response["Permissions-Policy"]
        assert response["X-Frame-Options"] == "DENY"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["Cache-Control"] == "no-store"

    def test_swagger_page_not_broken_by_api_policy(self):
        response = APIClient().get("/api/docs/")
        assert "Content-Security-Policy" not in response


def test_json_formatter_includes_extras_and_request_id():
    record = logging.makeLogRecord(
        {
            "name": "apps.requests",
            "levelname": "INFO",
            "msg": "GET %s",
            "args": ("/x",),
            "status": 200,
            "request_id": "abc123",
        }
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "GET /x"
    assert payload["status"] == 200 and payload["request_id"] == "abc123"
