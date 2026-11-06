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
