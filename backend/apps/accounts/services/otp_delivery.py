"""Delivers OTP messages by email or SMS. Never logs the code itself."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.accounts.choices import OTPChannel, OTPPurpose
from apps.accounts.services.sms import send_sms

logger = logging.getLogger(__name__)


class OTPDeliveryError(Exception):
    """The OTP message could not be handed to the email/SMS provider."""


def _context(**extra) -> dict:
    return {
        "institute_name": settings.INSTITUTE_NAME,
        "ttl_minutes": settings.OTP_TTL_SECONDS // 60,
        **extra,
    }


def _send(
    channel: str, to: str, *, subject: str, template: str, sms_text: str, context: dict
) -> None:
    try:
        if channel == OTPChannel.EMAIL:
            body = render_to_string(template, context)
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to],
                fail_silently=False,
            )
        else:
            send_sms(to, sms_text)
    except Exception as exc:
        logger.exception("OTP message delivery failed via %s", channel)
        raise OTPDeliveryError from exc


def deliver_otp(*, channel: str, to: str, code: str, purpose: str) -> None:
    action = {
        OTPPurpose.REGISTER: "registration",
        OTPPurpose.LOGIN: "login",
        OTPPurpose.GOOGLE_LINK: "Google sign-in verification",
        OTPPurpose.CONTACT_CHANGE: "contact verification",
    }[purpose]
    context = _context(code=code, action=action)
    _send(
        channel,
        to,
        subject=f"Your {settings.INSTITUTE_NAME} {action} code",
        template="accounts/email/otp.txt",
        sms_text=(
            f"{code} is your {settings.INSTITUTE_NAME} {action} code. "
            f"Valid for {context['ttl_minutes']} minutes. Do not share it with anyone."
        ),
        context=context,
    )


def deliver_already_registered_notice(*, channel: str, to: str) -> None:
    """
    Sent instead of a registration OTP when the email/phone already has an
    account. The API response stays identical either way, so nobody can use
    the registration form to discover who is registered; only the real owner
    of the inbox/phone learns it.
    """
    _send(
        channel,
        to,
        subject=f"You already have a {settings.INSTITUTE_NAME} account",
        template="accounts/email/already_registered.txt",
        sms_text=(
            f"Someone tried to register with this number at {settings.INSTITUTE_NAME}, "
            "but it already has an account. Please log in instead."
        ),
        context=_context(),
    )


def deliver_contact_changed_notice(
    *, channel: str, to: str, what: str, new_value_masked: str | None
) -> None:
    """
    Tell the OLD email/phone that it was replaced or removed, so an account
    takeover can't happen silently. `what` is "email address" or "phone number".
    """
    change = f"changed to {new_value_masked}" if new_value_masked else "removed"
    _send(
        channel,
        to,
        subject=f"Your {settings.INSTITUTE_NAME} {what} was {'changed' if new_value_masked else 'removed'}",
        template="accounts/email/contact_changed.txt",
        sms_text=(
            f"The {what} on your {settings.INSTITUTE_NAME} account was {change}. "
            "If this wasn't you, contact the institute immediately."
        ),
        context=_context(what=what, change=change),
    )
