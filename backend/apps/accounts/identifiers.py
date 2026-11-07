"""
Normalisation of the identifiers people sign in with.

Every email/phone is converted to ONE canonical form before it is stored,
looked up or rate-limited, so " A@X.com " and "a@x.com", or "98765 43210"
and "+919876543210", are always the same identity.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.accounts.choices import OTPChannel

E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_PHONE_SEPARATORS = re.compile(r"[\s\-().]")


def normalize_email(raw: str) -> str:
    value = (raw or "").strip().lower()
    validate_email(value)  # raises ValidationError
    return value


def normalize_phone(raw: str) -> str:
    """
    Return the number in E.164 form (+<country code><number>).

    Accepts: "+91 98765-43210", "0091 9876543210", and a bare 10-digit
    number "9876543210" (prefixed with DEFAULT_PHONE_COUNTRY_CODE).
    """
    value = _PHONE_SEPARATORS.sub("", (raw or "").strip())
    if value.startswith("00"):
        value = "+" + value[2:]
    elif re.fullmatch(r"\d{10}", value):
        value = settings.DEFAULT_PHONE_COUNTRY_CODE + value
    if not E164_PATTERN.match(value):
        raise ValidationError(
            "Enter a valid phone number with country code, e.g. +919876543210."
        )
    return value


def normalize_identifier(channel: str, raw: str) -> str:
    if channel == OTPChannel.EMAIL:
        return normalize_email(raw)
    if channel == OTPChannel.PHONE:
        return normalize_phone(raw)
    raise ValidationError("Unsupported channel.")


def mask_email(email: str) -> str:
    """'het310304@gmail.com' -> 'h*******4@gmail.com' (for "code sent to ..." messages)."""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked = local[:1] + "*"
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"


def user_field_for(channel: str) -> str:
    """The User model field that stores identifiers of this channel."""
    return "email" if channel == OTPChannel.EMAIL else "phone"
