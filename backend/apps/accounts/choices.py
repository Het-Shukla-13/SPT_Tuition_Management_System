from django.db import models


class OTPChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    PHONE = "PHONE", "Phone"


class OTPPurpose(models.TextChoices):
    """
    Why an OTP was issued. An OTP only works for the purpose it was issued for.

    There is no REGISTER purpose: the platform is invite-only, so accounts are
    created by the owner/admins, never through an OTP.
    """

    LOGIN = "LOGIN", "Login"
    # Proves ownership of the email before a Google account is linked to it.
    # Issued only by the Google sign-in flow, never by the public OTP endpoint.
    GOOGLE_LINK = "GOOGLE_LINK", "Google account linking"
    # Proves ownership of a NEW email/phone before it is attached to the
    # logged-in user's account. Issued only by the account-settings flow.
    CONTACT_CHANGE = "CONTACT_CHANGE", "Email/phone change"


# Purposes a client may request directly via POST /auth/otp/request/.
PUBLIC_OTP_PURPOSES = [
    (OTPPurpose.LOGIN.value, OTPPurpose.LOGIN.label),
]
