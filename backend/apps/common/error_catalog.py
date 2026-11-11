"""
The catalogue of every `error_code` the API can return, for the frontend.

Generated from the code itself (every APIException subclass, plus the few
codes passed explicitly), so it can't silently drift: `docs/frontend/error-codes.md`
is rewritten by `python manage.py error_codes`, and a test fails if the
committed file is out of date.
"""

import importlib
import pkgutil
from dataclasses import dataclass
from pathlib import Path

from django.apps import apps
from django.conf import settings
from rest_framework.exceptions import APIException

DOC_PATH = Path(settings.BASE_DIR) / "docs" / "frontend" / "error-codes.md"

# Codes produced without an exception class of their own.
EXTRA_CODES = {
    "INTERNAL_ERROR": (500, "An unexpected error occurred. Please try again later."),
    "SESSION_EXPIRED": (
        401,
        "This login has ended (logged out, or too old). Log in again.",
    ),
    "NO_ACTIVE_ACCOUNT": (401, "The account no longer exists or was deactivated."),
}
# Base/DRF codes our exception handler never emits (it maps them to others).
HIDDEN_CODES = {"INVALID", "ERROR"}

# What the screen should do, by status, unless overridden below.
DEFAULT_ACTION = {
    400: "Show `message`.",
    401: "Call `token/refresh/` once and retry; if that fails, go to the login page.",
    403: "Show `message` (not allowed). Don't retry.",
    404: "Show a 'not found' state.",
    405: "Bug in the frontend: wrong HTTP method.",
    406: "Bug in the frontend: send `Accept: application/json`.",
    409: "Show `message`; the data changed or already exists.",
    415: "Bug in the frontend: send JSON or multipart form data.",
    429: "Show `message`; wait `errors.retry_after_seconds` before retrying.",
    500: "Show a generic error with the `X-Request-ID` so it can be traced.",
    503: "Show `message`; let the user retry shortly.",
}
ACTION_OVERRIDES = {
    "VALIDATION_ERROR": "Show each entry of `errors` (field -> messages) next to its form field.",
    "ACCOUNT_DISABLED": "Log out and show `message` on the login page.",
    "SESSION_EXPIRED": "Go to the login page; say the session ended.",
    "NO_ACTIVE_ACCOUNT": "Go to the login page; show `message`.",
    "TOKEN_NOT_VALID": DEFAULT_ACTION[401],
    "CSRF_HEADER_MISSING": "Bug in the frontend: send `X-Requested-With: XMLHttpRequest` on refresh.",
    "OTP_COOLDOWN": "Show a countdown from `errors.retry_after_seconds`, then enable 'Resend'.",
    "OTP_ATTEMPTS_EXCEEDED": "Ask the user to request a new code.",
    "OTP_INVALID": "Show `message` under the code box; let them retry.",
    "OTP_EXPIRED": "Ask the user to request a new code.",
    "POSSIBLE_DUPLICATE_STUDENT": "Show the candidates in `errors`; resend with `confirm_duplicate: true` if the admin confirms.",
    "DUPLICATE_DOCUMENT": "Ask to confirm; resend with `confirm_duplicate: true`.",
    "IDEMPOTENCY_CONFLICT": "Bug in the frontend: generate a new Idempotency-Key per new payment.",
    "ANSWER_KEY_LOCKED": "Show when it unlocks (test start + duration).",
    "GOOGLE_UNAVAILABLE": "Offer email OTP login instead.",
    "GOOGLE_NOT_CONFIGURED": "Hide the Google button; use email OTP.",
    "EMAIL_REQUIRED": "Show `message`: an email is needed while SMS is off.",
    "INVALID_CREDENTIALS": 'Show `message` under the form; offer "Set or reset password".',
    "LOGIN_LOCKED": "Show `message` with a countdown from `errors.retry_after_seconds`.",
    "LOGIN_TICKET_INVALID": "Go back to the email + password step.",
    "WRONG_PASSWORD": "Show `message` under the current-password field.",
    "EMAIL_LOGIN_NEEDS_PASSWORD": "Bug in the frontend: email logins use auth/login/.",
    "DRIVE_API_DISABLED": "Show `message`; the owner must fix the Drive setup.",
    "THROTTLE_UNAVAILABLE": DEFAULT_ACTION[503],
}


@dataclass(frozen=True)
class ErrorCode:
    code: str
    status: int
    message: str
    action: str


def _import_all_app_modules() -> None:
    """Exception classes must be imported to be found as subclasses."""
    for config in apps.get_app_configs():
        if not config.name.startswith("apps."):
            continue
        for module in pkgutil.walk_packages([config.path], prefix=f"{config.name}."):
            if any(
                part in module.name for part in (".tests", ".migrations", ".management")
            ):
                continue
            importlib.import_module(module.name)


def _subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def collect() -> list[ErrorCode]:
    _import_all_app_modules()
    found: dict[str, tuple[int, str]] = {}
    for cls in _subclasses(APIException):
        code = str(cls.default_code).upper()
        if code not in HIDDEN_CODES:
            found.setdefault(code, (cls.status_code, str(cls.default_detail)))
    for code, value in EXTRA_CODES.items():
        found.setdefault(code, value)
    return sorted(
        (
            ErrorCode(
                code=code,
                status=status,
                message=" ".join(message.split()),
                action=ACTION_OVERRIDES.get(
                    code, DEFAULT_ACTION.get(status, "Show `message`.")
                ),
            )
            for code, (status, message) in found.items()
        ),
        key=lambda e: (e.status, e.code),
    )


def render() -> str:
    lines = [
        "# API error codes",
        "",
        "<!-- Generated by `python manage.py error_codes`. Do not edit by hand. -->",
        "",
        "Every failed response has `success: false`, an `error_code` from this list, a",
        "human-readable `message` (safe to show to users) and sometimes `errors` with",
        "details. Branch on `error_code`, never on `message` text.",
        "",
        "| Status | error_code | Default message | What the frontend should do |",
        "|---|---|---|---|",
    ]
    for e in collect():
        message = e.message.replace("|", "\\|")
        lines.append(f"| {e.status} | `{e.code}` | {message} | {e.action} |")
    return "\n".join(lines) + "\n"
