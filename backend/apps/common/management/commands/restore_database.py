"""
Restore the database from a backup. DESTRUCTIVE: replaces all current data.

    python manage.py restore_database --list                      # local + Drive backups
    python manage.py restore_database backups/db-backup-....dump --confirm <db name>
    python manage.py restore_database --drive gdrive/<id> --confirm <db name>

`--confirm` must repeat the database name, so a restore can't happen by
accident or against the wrong database. The restore runs in one transaction:
if anything fails, the database is left exactly as it was.
"""

import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.common.backups import (
    BACKUP_PREFIX,
    BACKUP_SUFFIX,
    BackupError,
    restore_database,
)
from apps.common.storage import GoogleDriveStorage, drive_configured


class Command(BaseCommand):
    help = "Replace the database contents with a backup (local file or Google Drive)."

    def add_arguments(self, parser):
        parser.add_argument("dump", nargs="?", help="Path to a local .dump file.")
        parser.add_argument(
            "--drive", help="Storage name of a backup in Drive (gdrive/<id>)."
        )
        parser.add_argument(
            "--confirm", help="The database name, to confirm the overwrite."
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_backups",
            help="List available backups.",
        )

    def handle(self, *args, dump, drive, confirm, list_backups, **options):
        if list_backups:
            return self._list()
        if bool(dump) == bool(drive):
            raise CommandError("Give either a local dump path or --drive <name>.")
        db_name = connections["default"].settings_dict["NAME"]
        if confirm != db_name:
            raise CommandError(
                f"This ERASES database '{db_name}'. Re-run with --confirm {db_name}"
            )

        if dump:
            path = Path(dump)
            if not path.is_file():
                raise CommandError(f"No such file: {path}")
            self._restore(path)
            return

        if not drive_configured():
            raise CommandError("Google Drive isn't connected.")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"download{BACKUP_SUFFIX}"
            with GoogleDriveStorage().open(drive) as src, path.open("wb") as dst:
                for chunk in src.chunks():
                    dst.write(chunk)
            self._restore(path)

    def _restore(self, path: Path):
        self.stdout.write(f"Restoring from {path} ...")
        try:
            restore_database(path)
        except BackupError as exc:
            raise CommandError(f"Restore failed, database unchanged: {exc}") from None
        self.stdout.write(self.style.SUCCESS("Restore complete."))

    def _list(self):
        local = sorted(
            Path(settings.BACKUP_DIR).glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"),
            reverse=True,
        )
        self.stdout.write("Local backups (newest first):")
        for path in local:
            self.stdout.write(f"  {path}  ({path.stat().st_size / 1024:.0f} KB)")
        if not local:
            self.stdout.write("  (none)")
        if drive_configured():
            self.stdout.write("Google Drive backups (newest first):")
            for name in GoogleDriveStorage().list_files(BACKUP_PREFIX):
                self.stdout.write(f"  {name}")
