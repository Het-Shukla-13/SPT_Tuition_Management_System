"""
Rate limiting with an explicit cache-outage policy (pattern from Labe1 Label_Auth).

DRF's throttles read/write the cache with no error handling, so if the cache
is unreachable the exception escapes as a bare 500. Instead, every throttle
here declares what should happen when its limit cannot be evaluated:

* ``fail_open = True``  — the limit only smooths load; correctness is
  guaranteed elsewhere. The request is allowed and the failure is logged.
* ``fail_open = False`` — the limit is what stops abuse (e.g. OTP requests
  that send email/SMS, OTP guessing). Losing it must not open the gate, so
  the request is refused with a clean 503 + Retry-After.

Rule of thumb for a new throttle: if this limit vanished for ten minutes,
would the worst case be abuse of something unauthenticated? Then fail closed.
"""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.throttling import (
    AnonRateThrottle,
    ScopedRateThrottle,
    UserRateThrottle,
)

logger = logging.getLogger(__name__)

THROTTLE_UNAVAILABLE_RETRY_AFTER = 30  # seconds


class ThrottleBackendUnavailable(APIException):
    """
    The limit could not be evaluated. Deliberately 503, not 429.

    Subclasses DRF's APIException directly (not apps.common.exceptions):
    DRF imports this module while loading its own views, which our exception
    module also imports, so importing it here would be circular.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "Rate limiting is temporarily unavailable, so this request cannot be "
        "processed. Please try again shortly."
    )
    default_code = "THROTTLE_UNAVAILABLE"

    def __init__(self):
        super().__init__()
        self.wait = THROTTLE_UNAVAILABLE_RETRY_AFTER


class ResilientThrottleMixin:
    """Mix in *before* a DRF throttle. Subclasses must set ``fail_open``."""

    fail_open: bool  # no default on purpose: someone must decide

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception:
            scope = getattr(self, "scope", None) or type(self).__name__
            if self.fail_open:
                logger.exception(
                    "Throttle backend unavailable for scope=%s - failing OPEN.", scope
                )
                return True
            logger.exception(
                "Throttle backend unavailable for scope=%s - failing CLOSED (503).",
                scope,
            )
            raise ThrottleBackendUnavailable() from None


class ResilientAnonRateThrottle(ResilientThrottleMixin, AnonRateThrottle):
    """Global per-IP limit for anonymous callers. Smooths load: fail open."""

    fail_open = True


class ResilientUserRateThrottle(ResilientThrottleMixin, UserRateThrottle):
    """Global per-user limit for authenticated callers. Smooths load: fail open."""

    fail_open = True


class ResilientScopedRateThrottle(ResilientThrottleMixin, ScopedRateThrottle):
    """
    Per-view limit selected by ``throttle_scope`` on the view. FAIL CLOSED:
    scoped limits guard sensitive public endpoints (OTP request/verify).
    """

    fail_open = False
