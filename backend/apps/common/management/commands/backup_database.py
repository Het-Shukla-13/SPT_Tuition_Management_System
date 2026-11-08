"""
Back up the database.

    python manage.py backup_database            # dump + copy to Google Drive + prune
    python manage.py backup_database --local-only

Writes a compressed pg_dump to BACKUP_DIR and, if Google Drive is connected
(and BACKUP_TO_DRIVE is on), uploads a copy to the private Drive folder so a
dead server doesn't take the backups with it. Keeps the newest BACKUP_KEEP
dumps in each place. Runs nightly via `run_scheduler`.
"""

import logging

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.common.backups import BACKUP_PREFIX, BackupError, dump_database, prune_local
from apps.common.storage import GoogleDriveStorage, drive_configured

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Dump the database to BACKUP_DIR and (if connected) Google Drive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--local-only", action="store_true", help="Skip the Drive upload."
        )

    def handle(self, *args, local_only, **options):
        try:
            path = dump_database(settings.BACKUP_DIR)
        except BackupError as exc:
            logger.error("Database backup FAILED: %s", exc)
            raise CommandError(str(exc)) from None
        size_kb = path.stat().st_size / 1024
        logger.info("Database backup written: %s (%.0f KB)", path.name, size_kb)
        self.stdout.write(f"Backup written: {path} ({size_kb:.0f} KB)")

        for old in prune_local(settings.BACKUP_DIR, settings.BACKUP_KEEP):
            self.stdout.write(f"Removed old local backup {old.name}")

        if local_only or not settings.BACKUP_TO_DRIVE:
            return
        if not drive_configured():
            self.stdout.write(
                "Google Drive not connected: backup kept on this machine only."
            )
            return

        drive = GoogleDriveStorage()
        try:
            with path.open("rb") as fh:
                drive.save(path.name, File(fh))
            for old in drive.list_files(BACKUP_PREFIX)[settings.BACKUP_KEEP :]:
                drive.delete(old)
        except Exception as exc:
            # The local dump exists; report loudly but don't pretend it all failed.
            logger.error("Backup upload to Google Drive FAILED: %s", exc)
            raise CommandError(f"Local backup OK, Drive upload failed: {exc}") from None
        logger.info("Database backup copied to Google Drive: %s", path.name)
        self.stdout.write("Copied to Google Drive.")
