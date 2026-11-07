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


def deliver_invite(*, channel: str, to: str, first_name: str, role_label: str) -> None:
    """
    "You've been added" message for a newly created login. Contains no code
    and no link: the person simply logs in with this email/phone (OTP).
    """
    _send(
        channel,
        to,
        subject=f"You've been added to {settings.INSTITUTE_NAME}",
        template="accounts/email/invite.txt",
        sms_text=(
            f"Hi {first_name}, you've been added to {settings.INSTITUTE_NAME} as a "
            f"{role_label}. Log in with this number using a one-time code."
        ),
        context=_context(first_name=first_name, role_label=role_label),
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
