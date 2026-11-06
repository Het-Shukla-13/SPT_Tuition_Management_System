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
