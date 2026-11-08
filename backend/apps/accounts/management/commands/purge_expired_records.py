"""
Delete auth records that are finished and past their retention period.

    python manage.py purge_expired_records

- OTP challenges older than OTP_RETENTION_DAYS (they expire within minutes;
  the rows are only an audit trail).
- Login sessions that ended (revoked or expired) more than
  SESSION_RETENTION_DAYS ago. Active sessions are never touched.
- Expired JWT refresh-token records (SimpleJWT's blacklist tables).

Runs nightly via `run_scheduler`. Safe to run any time.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import OTPChallenge, UserSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete old OTP challenges, ended sessions and expired token records."

    def handle(self, *args, **options):
        now = timezone.now()
        otp_cutoff = now - timedelta(days=settings.OTP_RETENTION_DAYS)
        session_cutoff = now - timedelta(days=settings.SESSION_RETENTION_DAYS)

        otps, _ = OTPChallenge.objects.filter(created_at__lt=otp_cutoff).delete()
        sessions, _ = UserSession.objects.filter(
            Q(revoked_at__lt=session_cutoff) | Q(expires_at__lt=session_cutoff)
        ).delete()
        call_command("flushexpiredtokens", verbosity=0)

        logger.info("Purged %s OTP challenges and %s ended sessions", otps, sessions)
        self.stdout.write(
            f"Deleted {otps} OTP challenges and {sessions} ended sessions."
        )
