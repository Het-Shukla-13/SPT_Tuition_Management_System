"""Authentication errors. Each maps to a stable `error_code` the frontend can switch on."""

from rest_framework import status

from apps.common.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    ServiceUnavailableError,
)


class OTPInvalid(AppException):
    # Same message whether the code is wrong or no OTP exists for the
    # identifier, so the response never reveals whether an account exists.
    default_detail = "The OTP is incorrect or has expired."
    default_code = "OTP_INVALID"


class OTPExpired(AppException):
    default_detail = "This OTP has expired. Please request a new one."
    default_code = "OTP_EXPIRED"


class OTPAttemptsExceeded(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many incorrect attempts. Please request a new OTP."
    default_code = "OTP_ATTEMPTS_EXCEEDED"


class _WaitException(AppException):
    """Carries `wait` (seconds): rendered as a Retry-After header + body field."""

    def __init__(self, wait: int):
        super().__init__()
        self.wait = wait


class OTPCooldown(_WaitException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Please wait before requesting another OTP."
    default_code = "OTP_COOLDOWN"


class OTPRequestLimitReached(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many OTP requests. Please try again later."
    default_code = "OTP_REQUEST_LIMIT_REACHED"


class OTPDeliveryFailed(ServiceUnavailableError):
    default_detail = "We couldn't send the OTP right now. Please try again shortly."
    default_code = "OTP_DELIVERY_FAILED"


class OTPServiceUnavailable(ServiceUnavailableError):
    """The OTP rate-limit store can't be read: refuse rather than allow (fail closed)."""

    default_detail = (
        "OTP verification is temporarily unavailable. Please try again shortly."
    )
    default_code = "OTP_TEMPORARILY_UNAVAILABLE"


class AccountAlreadyExists(ConflictError):
    default_detail = (
        "An account with these details already exists. Please log in instead."
    )
    default_code = "ACCOUNT_ALREADY_EXISTS"


class AccountDisabled(ForbiddenError):
    default_detail = "This account has been disabled. Please contact the institute."
    default_code = "ACCOUNT_DISABLED"


class InvalidRefreshToken(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The refresh token is invalid."
    default_code = "INVALID_REFRESH_TOKEN"
