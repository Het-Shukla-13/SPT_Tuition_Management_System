"""
Google Drive file storage (Phase 6, owner decision 2026-11-08).

A Django Storage backend, so the rest of the code (FileFields on test papers,
notes, student photos) doesn't know or care where files live.

- Files are uploaded into ONE private Drive folder of the owner's account.
- Scope `drive.file`: the app can only see files it created itself, never the
  rest of the owner's Drive.
- The stored file name is `gdrive/<drive-file-id>`; like Labe1 we keep only
  the key, never a URL. Files are never shared or made public: the backend
  downloads them after its own permission checks and streams them to the user.
- If Google can't be reached, or the connection was revoked, requests fail
  with a clean 503 (and a log entry telling the owner to reconnect).

Settings (.env): GOOGLE_DRIVE_CLIENT_ID, GOOGLE_DRIVE_CLIENT_SECRET,
GOOGLE_DRIVE_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID. Set them up with
`python manage.py google_drive_connect`.
"""

import json
import logging
import mimetypes
import tempfile

from django.conf import settings
from django.core.files import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from apps.common.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105 (a public URL, not a secret)
API = "https://www.googleapis.com/drive/v3/files"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
PREFIX = "gdrive/"
TIMEOUT = (10, 120)  # connect, read (seconds)


class FileStorageUnavailable(ServiceUnavailableError):
    default_detail = (
        "File storage is temporarily unavailable. Please try again shortly."
    )
    default_code = "FILE_STORAGE_UNAVAILABLE"


def drive_configured() -> bool:
    return all(
        getattr(settings, name, "")
        for name in (
            "GOOGLE_DRIVE_CLIENT_ID",
            "GOOGLE_DRIVE_CLIENT_SECRET",
            "GOOGLE_DRIVE_REFRESH_TOKEN",
            "GOOGLE_DRIVE_FOLDER_ID",
        )
    )


def drive_session():
    """An HTTP session that adds (and refreshes) the owner's Google access token."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials

    credentials = Credentials(
        token=None,
        refresh_token=settings.GOOGLE_DRIVE_REFRESH_TOKEN,
        client_id=settings.GOOGLE_DRIVE_CLIENT_ID,
        client_secret=settings.GOOGLE_DRIVE_CLIENT_SECRET,
        token_uri=TOKEN_URI,
        scopes=DRIVE_SCOPES,
    )
    return AuthorizedSession(credentials)


def file_id(name: str) -> str:
    return name[len(PREFIX) :] if name.startswith(PREFIX) else name


@deconstructible
class GoogleDriveStorage(Storage):
    def __init__(self, folder_id: str | None = None, session_factory=None):
        self.folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        self._session_factory = session_factory or drive_session
        self._session = None

    # ── plumbing ────────────────────────────────────────────
    @property
    def session(self):
        if self._session is None:
            self._session = self._session_factory()
        return self._session

    def _call(self, method: str, url: str, expected=(200,), **kwargs):
        from google.auth.exceptions import RefreshError, TransportError

        try:
            response = self.session.request(method, url, timeout=TIMEOUT, **kwargs)
        except RefreshError:
            logger.error(
                "Google Drive connection was revoked or expired. Run "
                "`python manage.py google_drive_connect` to reconnect."
            )
            raise FileStorageUnavailable() from None
        except (TransportError, OSError):
            logger.exception("Google Drive is unreachable")
            raise FileStorageUnavailable() from None
        if response.status_code not in expected:
            logger.error(
                "Google Drive %s %s -> %s: %s",
                method,
                url,
                response.status_code,
                response.text[:300],
            )
            if response.status_code == 404:
                raise FileNotFoundError(url)
            raise FileStorageUnavailable()
        return response

    # ── Storage API ─────────────────────────────────────────
    def _save(self, name, content):
        """Resumable upload (works for any size), into the private folder."""
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        metadata = {
            "name": name.replace("/", "_"),
            "parents": [self.folder_id],
            "mimeType": mime,
        }
        start = self._call(
            "POST",
            f"{UPLOAD_API}?uploadType=resumable&fields=id",
            data=json.dumps(metadata),
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime,
            },
        )
        upload_url = start.headers["Location"]
        content.seek(0)
        response = self._call(
            "PUT",
            upload_url,
            expected=(200, 201),
            data=content.read(),
            headers={"Content-Type": mime},
        )
        return f"{PREFIX}{response.json()['id']}"

    def _open(self, name, mode="rb"):
        response = self._call("GET", f"{API}/{file_id(name)}?alt=media", stream=True)
        # Keep small files in memory, spill big ones to a temp file.
        buffer = tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024)
        for chunk in response.iter_content(chunk_size=256 * 1024):
            buffer.write(chunk)
        buffer.seek(0)
        return File(buffer, name=name)

    def delete(self, name):
        try:
            self._call("DELETE", f"{API}/{file_id(name)}", expected=(200, 204))
        except FileNotFoundError:
            pass

    def exists(self, name):
        # Drive ids are unique: a new upload never collides with an old name.
        return False

    def size(self, name):
        response = self._call("GET", f"{API}/{file_id(name)}?fields=size")
        return int(response.json().get("size", 0))

    def url(self, name):
        # Deliberately no public URL: files are served only by permission-checked endpoints.
        raise NotImplementedError("Files are served through the API, never by URL.")

    def create_folder(self, title: str) -> str:
        response = self._call(
            "POST",
            f"{API}?fields=id",
            json={"name": title, "mimeType": "application/vnd.google-apps.folder"},
        )
        return response.json()["id"]
