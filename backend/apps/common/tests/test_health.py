from unittest import mock

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHealth:
    def test_liveness_returns_ok_envelope(self, api_client):
        response = api_client.get(reverse("health-live"))

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == {"status": "ok"}
        assert body["error_code"] is None

    def test_readiness_ok_when_db_and_cache_reachable(self, api_client):
        response = api_client.get(reverse("health-ready"))

        assert response.status_code == 200
        assert response.json()["data"] == {"database": "ok", "cache": "ok"}

    def test_readiness_503_when_database_down(self, api_client):
        with mock.patch(
            "apps.common.views.ReadinessView._check_database",
            return_value="unavailable",
        ):
            response = api_client.get(reverse("health-ready"))

        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "SERVICE_UNAVAILABLE"
        assert body["errors"]["database"] == "unavailable"

    def test_api_responses_have_request_id_and_no_store(self, api_client):
        response = api_client.get(reverse("health-live"))

        assert len(response["X-Request-ID"]) >= 8
        assert response["Cache-Control"] == "no-store"

    def test_valid_incoming_request_id_is_echoed(self, api_client):
        response = api_client.get(
            reverse("health-live"), HTTP_X_REQUEST_ID="client-abc-12345"
        )
        assert response["X-Request-ID"] == "client-abc-12345"

    def test_malicious_request_id_is_replaced(self, api_client):
        response = api_client.get(
            reverse("health-live"), HTTP_X_REQUEST_ID="bad\nINJECTED log line"
        )
        assert "INJECTED" not in response["X-Request-ID"]
