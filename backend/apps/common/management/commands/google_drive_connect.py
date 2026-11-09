"""
One-time (and "reconnect") setup for Google Drive storage.

    python manage.py google_drive_connect

1. Needs GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET in backend/.env
   (a "Desktop app" OAuth client from Google Cloud).
2. Opens your browser: sign in with the Google account whose Drive should hold
   the files, and allow access. The app only gets `drive.file`: it can see
   files it creates, nothing else in your Drive.
3. Creates a private folder for the files (unless GOOGLE_DRIVE_FOLDER_ID is set)
   and writes GOOGLE_DRIVE_REFRESH_TOKEN / GOOGLE_DRIVE_FOLDER_ID into .env.
   The token is never printed.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.common.storage import (
    DRIVE_SCOPES,
    TOKEN_URI,
    FileStorageUnavailable,
    GoogleDriveStorage,
)

FOLDER_TITLE = "Chalkboard (Sai Personal Tuitions) - app files (do not edit)"


def _write_env(path: Path, values: dict) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines += [f"{k}={v}" for k, v in remaining.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Command(BaseCommand):
    help = "Connect (or reconnect) Google Drive as the file storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--port", type=int, default=0, help="Local port for Google's redirect."
        )

    def handle(self, *args, port, **options):
        from google.auth.transport.requests import AuthorizedSession
        from google_auth_oauthlib.flow import InstalledAppFlow

        client_id, client_secret = (
            settings.GOOGLE_DRIVE_CLIENT_ID,
            settings.GOOGLE_DRIVE_CLIENT_SECRET,
        )
        if not client_id or not client_secret:
            raise CommandError(
                "Put GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_CLIENT_SECRET (Desktop app OAuth client) "
                "in backend/.env first."
            )
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": TOKEN_URI,
                    "redirect_uris": ["http://localhost"],
                }
            },
            scopes=DRIVE_SCOPES,
        )
        self.stdout.write("Opening your browser. Sign in and allow access...")
        credentials = flow.run_local_server(
            port=port, access_type="offline", prompt="consent"
        )
        if not credentials.refresh_token:
            raise CommandError(
                "Google didn't return a refresh token. Run the command again."
            )

        values = {"GOOGLE_DRIVE_REFRESH_TOKEN": credentials.refresh_token}
        folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        if not folder_id:
            storage = GoogleDriveStorage(
                folder_id="", session_factory=lambda: AuthorizedSession(credentials)
            )
            try:
                folder_id = storage.create_folder(FOLDER_TITLE)
            except FileStorageUnavailable as exc:
                raise CommandError(
                    f"Signed in, but Drive refused: {exc.detail}"
                ) from None
            values["GOOGLE_DRIVE_FOLDER_ID"] = folder_id
            self.stdout.write(f'Created Drive folder "{FOLDER_TITLE}".')

        env_path = Path(settings.BASE_DIR) / ".env"
        _write_env(env_path, values)
        self.stdout.write(
            self.style.SUCCESS(
                f"Connected. Saved {', '.join(values)} to {env_path.name} (values not shown). "
                "Restart the server to start storing files in Google Drive."
            )
        )
