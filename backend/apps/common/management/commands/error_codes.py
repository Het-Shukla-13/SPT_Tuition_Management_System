"""
Regenerate the frontend's error-code catalogue.

    python manage.py error_codes           # rewrite docs/frontend/error-codes.md
    python manage.py error_codes --check   # fail if the file is out of date (CI)
"""

from django.core.management.base import BaseCommand, CommandError

from apps.common.error_catalog import DOC_PATH, render


class Command(BaseCommand):
    help = "Write docs/frontend/error-codes.md from the exception classes."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true")

    def handle(self, *args, check, **options):
        content = render()
        current = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        if check:
            if current != content:
                raise CommandError(
                    "docs/frontend/error-codes.md is out of date: run "
                    "`python manage.py error_codes`."
                )
            self.stdout.write("Error-code catalogue is up to date.")
            return
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(content, encoding="utf-8", newline="\n")
        self.stdout.write(f"Wrote {DOC_PATH}")
