"""
Standard API response envelope.

Every endpoint returns the same top-level shape so the frontend can handle
success and failure uniformly:

    {
        "success": true | false,
        "message": "Human-readable summary",
        "data": {...} | [...] | null,
        "errors": {...} | null,        # field-level details on failure
        "error_code": "UPPER_SNAKE" | null,
        "meta": {...} | null           # pagination info on list endpoints
    }
"""

from rest_framework import status
from rest_framework.response import Response


def build_envelope(
    *,
    success: bool,
    message: str,
    data=None,
    errors=None,
    error_code: str | None = None,
    meta: dict | None = None,
) -> dict:
    return {
        "success": success,
        "message": message,
        "data": data,
        "errors": errors,
        "error_code": error_code,
        "meta": meta,
    }


class ApiResponse:
    """Helpers that wrap data in the standard envelope."""

    @staticmethod
    def success(
        data=None,
        message: str = "Success.",
        status_code: int = status.HTTP_200_OK,
        meta: dict | None = None,
        headers: dict | None = None,
    ) -> Response:
        return Response(
            build_envelope(success=True, message=message, data=data, meta=meta),
            status=status_code,
            headers=headers,
        )

    @staticmethod
    def created(data=None, message: str = "Created successfully.") -> Response:
        return ApiResponse.success(
            data=data, message=message, status_code=status.HTTP_201_CREATED
        )

    @staticmethod
    def error(
        message: str = "An error occurred.",
        error_code: str = "ERROR",
        errors=None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        headers: dict | None = None,
    ) -> Response:
        return Response(
            build_envelope(
                success=False, message=message, errors=errors, error_code=error_code
            ),
            status=status_code,
            headers=headers,
        )
