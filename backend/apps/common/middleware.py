"""Project-wide middleware."""

import re
import uuid

from apps.common.request_context import request_id_var

# Accept a client-supplied ID only if it looks sane; otherwise generate one.
# Prevents log injection through a crafted header.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

API_PATH_PREFIX = "/api/"


class RequestIDMiddleware:
    """
    Give every request a unique ID.

    - Reuses a valid incoming `X-Request-ID` header (useful behind a proxy),
      otherwise generates a UUID4.
    - Exposes it on `request.request_id`, in every log line, and in the
      `X-Request-ID` response header so a user-reported error can be matched
      to server logs.
    - Marks API responses `Cache-Control: no-store` so the browser never
      re-displays private data from its cache (e.g. after logout + Back).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)

        response["X-Request-ID"] = request_id
        if request.path.startswith(API_PATH_PREFIX):
            response["Cache-Control"] = "no-store"
        return response


# JSON API responses get a locked-down policy: they never need to load scripts,
# frames or anything else. (Files like PDFs are left alone so browser viewers work.)
API_CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'"
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        content_type = response.get("Content-Type", "")
        if request.path.startswith("/api/v1/") and content_type.startswith(
            "application/json"
        ):
            response.setdefault("Content-Security-Policy", API_CONTENT_SECURITY_POLICY)
        return response


class RequestLoggingMiddleware:
    """
    One line per request (pattern from Labe1's RequestLoggingMiddleware):
    method, path, status, duration, user id. Never logs query strings, bodies,
    headers or tokens. Requests slower than SLOW_REQUEST_MS are logged as warnings.
    """

    QUIET_PATHS = ("/api/v1/health/",)

    def __init__(self, get_response):
        import logging

        self.get_response = get_response
        self.logger = logging.getLogger("apps.requests")

    def __call__(self, request):
        import time

        from django.conf import settings

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        user = getattr(request, "user", None)  # DRF copies the JWT user here
        user_id = user.pk if user is not None and user.is_authenticated else None
        status = response.status_code
        message = "%s %s -> %s in %.0fms (user=%s)"
        args = (request.method, request.path, status, duration_ms, user_id)
        extra = {
            "http_method": request.method,
            "path": request.path,
            "status": status,
            "duration_ms": round(duration_ms),
            "user_id": user_id,
        }

        if status >= 500:
            self.logger.error(message, *args, extra=extra)
        elif duration_ms >= settings.SLOW_REQUEST_MS:
            self.logger.warning("SLOW " + message, *args, extra=extra)
        elif status >= 400:
            self.logger.warning(message, *args, extra=extra)
        elif request.path.startswith(self.QUIET_PATHS):
            self.logger.debug(message, *args, extra=extra)
        else:
            self.logger.info(message, *args, extra=extra)
        return response
