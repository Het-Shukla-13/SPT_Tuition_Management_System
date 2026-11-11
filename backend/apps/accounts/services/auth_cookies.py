"""
The refresh token travels in an HttpOnly cookie (Phase 9).

Why: a refresh token lives for days. If the browser app had to keep it in
localStorage, any script injected into the page (an XSS bug, a compromised
npm package) could read it and stay logged in as that user. An HttpOnly
cookie is stored by the browser but is invisible to JavaScript.

- The access token (15 min) is still returned in the body; the frontend keeps
  it in memory only.
- The cookie's Path is the auth endpoints, so it isn't sent with ordinary
  API calls.
- REFRESH_TOKEN_IN_BODY additionally returns the refresh token in the JSON
  body (development: Swagger works as before; off in production).
- Because the browser sends cookies automatically, endpoints that ACT on the
  cookie require the `X-Requested-With` header: another website can't add a
  custom header to a cross-site request without passing our CORS check.
"""

from django.conf import settings

from apps.common.exceptions import AppException
from apps.common.responses import ApiResponse

CSRF_HEADER = "X-Requested-With"


class CsrfHeaderMissing(AppException):
    status_code = 403
    default_detail = (
        f"Missing the {CSRF_HEADER} header required when using the login cookie."
    )
    default_code = "CSRF_HEADER_MISSING"


def _max_age() -> int:
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response, refresh: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        max_age=_max_age(),
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def refresh_from_request(request, body_value: str | None) -> str | None:
    """
    The refresh token from the body (Swagger, tests, non-browser clients) or,
    failing that, from the cookie. Using the cookie requires the CSRF header.
    """
    if body_value:
        return body_value
    cookie = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
    if cookie and not request.headers.get(CSRF_HEADER):
        raise CsrfHeaderMissing()
    return cookie or None


def token_response(*, message: str, tokens: dict, extra: dict | None = None):
    """A login/refresh success response: access in the body, refresh in the cookie."""
    data = {**(extra or {}), "access": tokens["access"]}
    if settings.REFRESH_TOKEN_IN_BODY:
        data["refresh"] = tokens["refresh"]
    response = ApiResponse.success(message=message, data=data)
    set_refresh_cookie(response, tokens["refresh"])
    return response


# ── Trusted-device cookie (Phase 1.5) ─────────────────────────
def set_device_cookie(response, token: str) -> None:
    """Long-lived, HttpOnly, auth paths only: same protections as the refresh cookie."""
    response.set_cookie(
        settings.DEVICE_COOKIE_NAME,
        token,
        max_age=settings.TRUSTED_DEVICE_DAYS * 24 * 3600,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def clear_device_cookie(response) -> None:
    response.delete_cookie(
        settings.DEVICE_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
