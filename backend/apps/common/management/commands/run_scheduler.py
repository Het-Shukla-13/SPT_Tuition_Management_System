"""
Run the daily jobs in settings.SCHEDULED_JOBS, forever.

    python manage.py run_scheduler                 # the "scheduler" container
    python manage.py run_scheduler --run-now backup_database

A long-running process like Labe1's worker commands, instead of Celery
(which would need Redis plus worker and beat processes) or system cron (which
drops environment variables and logs nowhere useful). Each job is an ordinary
management command, so it can also be run by hand.

- Times are in TIME_ZONE (Asia/Kolkata).
- A failing job is logged and the scheduler keeps going.
- Stops cleanly on SIGTERM (`docker compose stop`), never mid-job.
"""

import logging
import signal
import threading
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)


def parse_at(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def next_run(at: time, now: datetime) -> datetime:
    """The next moment (strictly after `now`) the wall clock shows `at`."""
    candidate = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = timezone.make_aware(
            datetime.combine(candidate.date() + timedelta(days=1), at),
            now.tzinfo,
        )
    return candidate


def run_job(command: str) -> bool:
    close_old_connections()
    started = timezone.now()
    try:
        call_command(command)
    except BaseException as exc:  # noqa: BLE001 - one bad job must not kill the loop
        if isinstance(exc, KeyboardInterrupt):
            raise
        logger.exception("Scheduled job %s FAILED", command)
        return False
    finally:
        close_old_connections()
    seconds = (timezone.now() - started).total_seconds()
    logger.info("Scheduled job %s finished in %.1fs", command, seconds)
    return True


class Command(BaseCommand):
    help = "Run the scheduled daily jobs (backups, cleanup)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-now", metavar="COMMAND", help="Run one job immediately and exit."
        )

    def handle(self, *args, run_now, **options):
        if run_now:
            run_job(run_now)
            return

        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())

        jobs = [
            (job["command"], parse_at(job["at"])) for job in settings.SCHEDULED_JOBS
        ]
        now = timezone.localtime()
        due = {command: next_run(at, now) for command, at in jobs}
        for command, when in sorted(due.items(), key=lambda item: item[1]):
            logger.info("Scheduler: %s next runs at %s", command, when.isoformat())

        while not stop.is_set():
            command = min(due, key=due.get)
            wait = (due[command] - timezone.localtime()).total_seconds()
            # Wake at least every minute so clock changes and SIGTERM are noticed.
            if wait > 0:
                stop.wait(min(wait, 60))
                continue
            run_job(command)
            at = dict(jobs)[command]
            due[command] = next_run(at, timezone.localtime())
        logger.info("Scheduler stopped.")
