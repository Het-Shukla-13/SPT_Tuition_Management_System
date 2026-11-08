"""
Move files saved on the local disk (before Google Drive was connected) into Drive.

    python manage.py migrate_files_to_drive --dry-run   # show what would move
    python manage.py migrate_files_to_drive             # move them

Covers test/notes PDFs (all versions) and student photos. Safe to re-run:
files already in Drive (names starting with "gdrive/") are skipped. Local
copies are kept; delete backend/media yourself once you've checked Drive.
"""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from apps.common.storage import PREFIX, GoogleDriveStorage, drive_configured


class Command(BaseCommand):
    help = "Copy locally stored files into Google Drive and point the records at them."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, dry_run, **options):
        from apps.learning.models import DocumentFile
        from apps.students.models import StudentProfile

        if not drive_configured():
            raise CommandError(
                "Google Drive isn't connected yet: run `python manage.py google_drive_connect`."
            )
        local = FileSystemStorage(location=settings.MEDIA_ROOT)
        drive = GoogleDriveStorage()
        moved = skipped = missing = 0

        targets = [
            (doc, "file")
            for doc in DocumentFile.objects.exclude(file__startswith=PREFIX)
        ]
        targets += [
            (student, "photo")
            for student in StudentProfile.all_objects.exclude(photo="")
            .exclude(photo__isnull=True)
            .exclude(photo__startswith=PREFIX)
        ]
        for obj, field in targets:
            name = getattr(obj, field).name
            if not local.exists(name):
                self.stderr.write(f"Missing on disk, skipped: {name}")
                missing += 1
                continue
            if dry_run:
                self.stdout.write(f"Would move: {name}")
                skipped += 1
                continue
            with local.open(name, "rb") as handle:
                new_name = drive.save(name, handle)
            model = type(obj)
            manager = getattr(
                model, "all_objects", model.objects
            )  # include soft-deleted students
            manager.filter(pk=obj.pk).update(**{field: new_name})
            moved += 1
            self.stdout.write(f"Moved: {name}")

        verb = "Would move" if dry_run else "Moved"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {moved or skipped} file(s); {missing} missing on disk."
            )
        )
