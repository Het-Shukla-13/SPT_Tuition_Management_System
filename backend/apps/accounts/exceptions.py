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


class CannotModifySelf(ForbiddenError):
    default_detail = "You cannot change your own role or account status."
    default_code = "CANNOT_MODIFY_SELF"


class OwnerAccountProtected(ForbiddenError):
    """Owner accounts are changed only by the owner themselves (or directly in the database)."""

    default_detail = "Owner accounts can't be changed by anyone else in the app."
    default_code = "OWNER_PROTECTED"


class AdminTargetRequiresOwner(ForbiddenError):
    default_detail = (
        "Only the institute owner account can modify another administrator."
    )
    default_code = "OWNER_REQUIRED"


class LastAdminProtected(ConflictError):
    default_detail = (
        "This is the last active administrator and cannot be demoted or deactivated."
    )
    default_code = "LAST_ADMIN"


class GoogleTokenInvalid(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "The Google sign-in could not be verified. Please try again."
    default_code = "GOOGLE_TOKEN_INVALID"


class GoogleEmailNotVerified(AppException):
    default_detail = "This Google account's email address is not verified with Google."
    default_code = "GOOGLE_EMAIL_NOT_VERIFIED"


class GoogleAccountConflict(ConflictError):
    default_detail = (
        "This account is already linked to a different Google account. "
        "Unlink it first, or sign in with the linked Google account."
    )
    default_code = "GOOGLE_ACCOUNT_CONFLICT"


class GoogleNotLinked(AppException):
    default_detail = "No Google account is linked to this account."
    default_code = "GOOGLE_NOT_LINKED"


class GoogleUnavailable(ServiceUnavailableError):
    default_detail = (
        "Google sign-in is temporarily unavailable. Please try again or use an OTP."
    )
    default_code = "GOOGLE_UNAVAILABLE"


class GoogleNotConfigured(ServiceUnavailableError):
    default_detail = "Google sign-in is not available right now."
    default_code = "GOOGLE_NOT_CONFIGURED"


class ContactUnchanged(AppException):
    default_detail = "This is already the email/phone on your account."
    default_code = "CONTACT_UNCHANGED"


class ContactInUse(ConflictError):
    default_detail = "This email/phone is already used by another account."
    default_code = "CONTACT_IN_USE"


class ContactNotSet(AppException):
    default_detail = "There is no email/phone of this type on the account."
    default_code = "CONTACT_NOT_SET"


class LastContactMethod(AppException):
    default_detail = (
        "You can't remove this: an account needs at least one email or phone to log in."
    )
    default_code = "LAST_CONTACT_METHOD"


class EmailRequiredWithoutSMS(AppException):
    """SMS is off: removing the email would leave the login unable to sign in."""

    default_detail = (
        "You can't remove the email: SMS isn't enabled yet, so it's the only "
        "way this account can sign in."
    )
    default_code = "EMAIL_REQUIRED"


class InviteAlreadyAccepted(AppException):
    default_detail = "This person has already logged in; no invite is needed."
    default_code = "INVITE_ALREADY_ACCEPTED"


class InvalidRefreshToken(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The refresh token is invalid."
    default_code = "INVALID_REFRESH_TOKEN"


# ── Password login (Phase 1.5) ───────────────────────────────
class InvalidCredentials(AppException):
    # One message for every failure (unknown email, wrong password, no password
    # set yet, deleted account), so the login form never reveals who has an account.
    default_detail = (
        "Email or password is incorrect. First time here or forgot your password? "
        'Use "Set or reset password".'
    )
    default_code = "INVALID_CREDENTIALS"


class LoginLocked(_WaitException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = (
        "Too many wrong passwords. Please wait a few minutes and try again."
    )
    default_code = "LOGIN_LOCKED"


class LoginTicketInvalid(AppException):
    default_detail = (
        "This sign-in has expired. Please enter your email and password again."
    )
    default_code = "LOGIN_TICKET_INVALID"


class WrongPassword(AppException):
    default_detail = "Your current password is incorrect."
    default_code = "WRONG_PASSWORD"


class EmailLoginNeedsPassword(AppException):
    default_detail = "Log in with your email and password."
    default_code = "EMAIL_LOGIN_NEEDS_PASSWORD"
