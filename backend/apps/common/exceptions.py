"""
Domain exceptions and the global DRF exception handler.

Services raise these exceptions; the handler turns *any* exception — ours,
DRF's, SimpleJWT's or an unexpected crash — into the standard error envelope.
Unexpected errors never leak internal details (stack traces, SQL) to clients;
they are logged with the request ID instead.
"""

import logging
import math

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler

from apps.common.responses import ApiResponse

logger = logging.getLogger(__name__)

# Response headers from DRF's own handling that clients rely on.
_PRESERVED_HEADERS = ("WWW-Authenticate", "Retry-After")


class AppException(exceptions.APIException):
    """
    Base class for domain errors raised by our services.

    Usage:
        raise ConflictError("This email is already registered.",
                            details={"email": ["Already registered."]})
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The request could not be processed."
    default_code = "BAD_REQUEST"

    def __init__(self, message=None, code=None, details=None):
        super().__init__(detail=message, code=code)
        self.details = details


class ValidationFailed(AppException):
    default_detail = "Validation failed."
    default_code = "VALIDATION_ERROR"


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The requested resource was not found."
    default_code = "NOT_FOUND"


class ForbiddenError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "PERMISSION_DENIED"


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "CONFLICT"


class ServiceUnavailableError(AppException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The service is temporarily unavailable. Please try again later."
    default_code = "SERVICE_UNAVAILABLE"


def _code_of(detail, fallback: str) -> str:
    return str(getattr(detail, "code", None) or fallback).upper()


def custom_exception_handler(exc, context):
    # Normalise Django's own exceptions into DRF ones so the code below
    # only ever deals with APIException instances.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)

    if response is None:
        # Not an API exception: a genuine bug or infrastructure failure.
        logger.exception("Unhandled exception in %s", context.get("view"))
        return ApiResponse.error(
            message="An unexpected error occurred. Please try again later.",
            error_code="INTERNAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    errors = None
    detail = getattr(exc, "detail", None)

    if isinstance(exc, exceptions.ValidationError):
        message = "Validation failed."
        code = "VALIDATION_ERROR"
        errors = response.data
    elif isinstance(detail, dict) and "detail" in detail:
        # SimpleJWT style: {"detail": "...", "code": "...", "messages": [...]}
        message = str(detail["detail"])
        code = str(detail.get("code") or exc.default_code).upper()
    elif isinstance(detail, (dict, list)):
        message = str(exc.default_detail)
        code = str(exc.default_code).upper()
        errors = response.data
    else:
        message = str(detail) if detail is not None else str(exc.default_detail)
        code = _code_of(detail, exc.default_code)

    if isinstance(exc, AppException) and exc.details:
        errors = exc.details
    # Throttled, OTP cooldowns and outage errors carry `wait` (seconds); DRF
    # already turned it into a Retry-After header, mirror it in the body.
    wait = getattr(exc, "wait", None)
    if wait is not None:
        errors = {"retry_after_seconds": math.ceil(wait)}

    if response.status_code >= 500:
        logger.error("API error %s: %s", code, message)
    else:
        logger.info("API error %s (%s): %s", code, response.status_code, message)

    headers = {h: response[h] for h in _PRESERVED_HEADERS if h in response}
    return ApiResponse.error(
        message=message,
        error_code=code,
        errors=errors,
        status_code=response.status_code,
        headers=headers,
    )
