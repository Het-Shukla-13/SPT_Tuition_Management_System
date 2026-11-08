"""
Pluggable SMS sending, mirroring how Django's EMAIL_BACKEND works.

settings.SMS_BACKEND names the class to use:
- ConsoleSMSBackend  - development: prints the message to the terminal.
- LocmemSMSBackend   - tests: keeps messages in memory for assertions.
- DisabledSMSBackend - production without an SMS provider: every send fails
  cleanly, so phone OTP answers "couldn't deliver" instead of printing codes.
- (later) a real gateway backend for production.
"""

import sys

from django.conf import settings
from django.utils.module_loading import import_string


class SMSDeliveryError(Exception):
    """The provider could not accept the message."""


class BaseSMSBackend:
    def send(self, to: str, message: str) -> None:
        raise NotImplementedError


class ConsoleSMSBackend(BaseSMSBackend):
    """Development only. Writes to stdout (not the logger) like Django's console email backend."""

    def send(self, to: str, message: str) -> None:
        sys.stdout.write(f"\n----- SMS to {to} -----\n{message}\n{'-' * 30}\n")
        sys.stdout.flush()


class LocmemSMSBackend(BaseSMSBackend):
    """Tests only. Sent messages are collected in `LocmemSMSBackend.outbox`."""

    outbox: list[dict] = []

    def send(self, to: str, message: str) -> None:
        LocmemSMSBackend.outbox.append({"to": to, "message": message})


class DisabledSMSBackend(BaseSMSBackend):
    """No SMS provider configured. Sending fails; nothing is printed or logged."""

    def send(self, to: str, message: str) -> None:
        raise SMSDeliveryError("SMS sending is not configured on this server.")


def send_sms(to: str, message: str) -> None:
    backend = import_string(settings.SMS_BACKEND)()
    backend.send(to, message)
