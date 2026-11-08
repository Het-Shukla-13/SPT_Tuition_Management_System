"""Google Drive storage backend, against an in-memory fake Drive (no network)."""

from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from google.auth.exceptions import RefreshError, TransportError

from apps.common.management.commands.google_drive_connect import _write_env
from apps.common.storage import FileStorageUnavailable, GoogleDriveStorage


class FakeDrive:
    """Just enough of the Drive v3 REST API for our storage class."""

    def __init__(self):
        self.files, self.calls, self.fail = {}, [], None

    def request(self, method, url, timeout=None, **kw):
        self.calls.append((method, url, kw.get("headers", {})))
        if self.fail:
            raise self.fail
        if method == "POST" and "uploadType=resumable" in url:
            return SimpleNamespace(
                status_code=200,
                headers={"Location": "https://upload/session-1"},
                text="",
            )
        if method == "PUT" and url == "https://upload/session-1":
            file_id = f"id{len(self.files) + 1}"
            self.files[file_id] = kw["data"]
            return SimpleNamespace(
                status_code=200, json=lambda: {"id": file_id}, text=""
            )
        file_id = url.split("/files/")[-1].split("?")[0]
        if file_id not in self.files:
            return SimpleNamespace(status_code=404, text="not found")
        if method == "GET" and "alt=media" in url:
            data = self.files[file_id]
            return SimpleNamespace(
                status_code=200, iter_content=lambda chunk_size: [data], text=""
            )
        if method == "GET" and "fields=size" in url:
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"size": str(len(self.files[file_id]))},
                text="",
            )
        if method == "DELETE":
            del self.files[file_id]
            return SimpleNamespace(status_code=204, text="")
        return SimpleNamespace(status_code=500, text="unexpected")


@pytest.fixture
def drive():
    return FakeDrive()


@pytest.fixture
def storage(drive):
    return GoogleDriveStorage(folder_id="folder-1", session_factory=lambda: drive)


def test_upload_returns_key_and_goes_to_private_folder(storage, drive):
    name = storage.save("documents/paper/abc.pdf", ContentFile(b"%PDF-1.7 data"))
    assert name == "gdrive/id1"
    assert drive.files["id1"] == b"%PDF-1.7 data"
    method, url, headers = drive.calls[0]
    assert headers["X-Upload-Content-Type"] == "application/pdf"


def test_download_size_delete(storage, drive):
    name = storage.save("x.pdf", ContentFile(b"hello"))
    with storage.open(name) as handle:
        assert handle.read() == b"hello"
    assert storage.size(name) == 5
    storage.delete(name)
    assert drive.files == {}
    storage.delete(name)  # already gone: no error


def test_missing_file_is_file_not_found(storage):
    with pytest.raises(FileNotFoundError):
        storage.open("gdrive/nope")


def test_no_public_urls(storage):
    with pytest.raises(NotImplementedError):
        storage.url("gdrive/id1")


@pytest.mark.parametrize(
    "error", [RefreshError("revoked"), TransportError("down"), OSError("net")]
)
def test_google_problems_become_503(storage, drive, error):
    drive.fail = error
    with pytest.raises(FileStorageUnavailable):
        storage.save("x.pdf", ContentFile(b"data"))


def test_write_env_updates_and_appends(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nGOOGLE_DRIVE_REFRESH_TOKEN=old\n", encoding="utf-8")
    _write_env(
        env, {"GOOGLE_DRIVE_REFRESH_TOKEN": "new", "GOOGLE_DRIVE_FOLDER_ID": "f1"}
    )
    assert env.read_text(encoding="utf-8").splitlines() == [
        "A=1",
        "GOOGLE_DRIVE_REFRESH_TOKEN=new",
        "GOOGLE_DRIVE_FOLDER_ID=f1",
    ]
