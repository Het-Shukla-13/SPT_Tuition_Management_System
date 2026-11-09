"""
Error pages for requests that never reach a DRF view: an unknown URL, a bad
Host header, a crash inside middleware. Under /api/ they answer with the
standard JSON envelope; everything else (the Django admin) keeps Django's
normal HTML pages.
"""

from django.http import JsonResponse
from django.views import defaults

from apps.common.middleware import API_PATH_PREFIX
from apps.common.responses import build_envelope


def _is_api(request) -> bool:
    return request.path.startswith(API_PATH_PREFIX)


def _json(status: int, code: str, message: str) -> JsonResponse:
    body = build_envelope(success=False, message=message, error_code=code)
    return JsonResponse(body, status=status)


def bad_request(request, exception=None):
    if _is_api(request):
        return _json(400, "BAD_REQUEST", "The request could not be understood.")
    return defaults.bad_request(request, exception)


def permission_denied(request, exception=None):
    if _is_api(request):
        return _json(403, "PERMISSION_DENIED", "You do not have permission to do this.")
    return defaults.permission_denied(request, exception)


def page_not_found(request, exception=None):
    if _is_api(request):
        return _json(404, "NOT_FOUND", "This API endpoint does not exist.")
    return defaults.page_not_found(request, exception)


def server_error(request):
    if _is_api(request):
        return _json(
            500,
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again later.",
        )
    return defaults.server_error(request)
