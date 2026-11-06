from django.http import Http404
from rest_framework import exceptions

from apps.common.exceptions import ConflictError, custom_exception_handler


def _handle(exc):
    return custom_exception_handler(exc, {"view": None})


def test_validation_error_returns_field_errors():
    response = _handle(exceptions.ValidationError({"email": ["Enter a valid email."]}))

    assert response.status_code == 400
    assert response.data["success"] is False
    assert response.data["error_code"] == "VALIDATION_ERROR"
    assert response.data["errors"] == {"email": ["Enter a valid email."]}


def test_not_authenticated_is_401_with_code():
    response = _handle(exceptions.NotAuthenticated())

    assert response.status_code == 401
    assert response.data["error_code"] == "NOT_AUTHENTICATED"


def test_django_404_is_wrapped():
    response = _handle(Http404())

    assert response.status_code == 404
    assert response.data["error_code"] == "NOT_FOUND"


def test_domain_exception_carries_details():
    response = _handle(
        ConflictError("Email already registered.", details={"email": ["Taken."]})
    )

    assert response.status_code == 409
    assert response.data["message"] == "Email already registered."
    assert response.data["error_code"] == "CONFLICT"
    assert response.data["errors"] == {"email": ["Taken."]}


def test_throttled_includes_retry_after():
    response = _handle(exceptions.Throttled(wait=30))

    assert response.status_code == 429
    assert response.data["errors"] == {"retry_after_seconds": 30}
    assert response["Retry-After"] == "30"


def test_unexpected_exception_does_not_leak_details():
    response = _handle(RuntimeError("database password is hunter2"))

    assert response.status_code == 500
    assert response.data["error_code"] == "INTERNAL_ERROR"
    assert "hunter2" not in str(response.data)
