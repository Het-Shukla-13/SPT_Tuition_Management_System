from django.db import models


class OTPChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    PHONE = "PHONE", "Phone"


class OTPPurpose(models.TextChoices):
    """
    Why an OTP was issued. An OTP only works for the purpose it was issued
    for, so a login OTP can never create an account and vice versa.
    """

    REGISTER = "REGISTER", "Registration"
    LOGIN = "LOGIN", "Login"
    # Proves ownership of the email before a Google account is linked to it.
    # Issued only by the Google sign-in flow, never by the public OTP endpoint.
    GOOGLE_LINK = "GOOGLE_LINK", "Google account linking"


# Purposes a client may request directly via POST /auth/otp/request/.
PUBLIC_OTP_PURPOSES = [
    (OTPPurpose.REGISTER.value, OTPPurpose.REGISTER.label),
    (OTPPurpose.LOGIN.value, OTPPurpose.LOGIN.label),
]
