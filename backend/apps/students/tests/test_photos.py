import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.academics.models import Board, School, Standard
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog
from apps.students.models import StudentAccess, StudentProfile


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return c


def image_file(fmt="PNG", size=(2000, 1500), name="me.png"):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    exif[0x8825] = {2: (23, 1, 0)}  # GPS info that must be stripped
    img.save(buf, format=fmt, exif=exif.tobytes()) if fmt == "JPEG" else img.save(
        buf, format=fmt
    )
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def setup(db):
    admin = User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)
    student = StudentProfile.objects.create(
        admission_number="P-1",
        first_name="Aarav",
        last_name="Shah",
        board=Board.objects.get(code="CBSE"),
        standard=Standard.objects.get(level=10),
        school=School.objects.create(name="DPS", city="Ahd"),
    )
    parent = User.objects.create_user(phone="+919876543210")
    StudentAccess.objects.create(user=parent, student=student)
    return admin, student, parent


def url(student):
    return f"/api/v1/admin/students/{student.pk}/photo/"


@pytest.mark.django_db
class TestPhotos:
    def test_upload_is_resized_reencoded_and_stripped(self, setup):
        admin, student, _ = setup
        response = client_for(admin).post(
            url(student),
            {"photo": image_file("JPEG", name="x.jpg")},
            format="multipart",
        )

        assert response.status_code == 200
        assert response.json()["data"]["has_photo"] is True
        student.refresh_from_db()
        with student.photo.open("rb") as handle:
            stored = Image.open(handle)
            assert stored.format == "JPEG"
            assert max(stored.size) == 800
            assert not stored.getexif()  # GPS/metadata gone
        assert AuditLog.objects.filter(action="STUDENT_PHOTO_CHANGED").exists()

    def test_fake_image_rejected(self, setup):
        admin, student, _ = setup
        fake = SimpleUploadedFile(
            "evil.png", b"MZ\x90 not an image", content_type="image/png"
        )
        response = client_for(admin).post(
            url(student), {"photo": fake}, format="multipart"
        )
        assert response.json()["error_code"] == "INVALID_PHOTO"

    def test_unsupported_format_rejected(self, setup):
        admin, student, _ = setup
        response = client_for(admin).post(
            url(student), {"photo": image_file("GIF", name="a.gif")}, format="multipart"
        )
        assert response.json()["error_code"] == "INVALID_PHOTO"

    def test_too_large_rejected(self, setup, settings):
        settings.MAX_PHOTO_SIZE_MB = 0
        admin, student, _ = setup
        response = client_for(admin).post(
            url(student), {"photo": image_file()}, format="multipart"
        )
        assert response.json()["error_code"] == "PHOTO_TOO_LARGE"

    def test_replace_view_remove_and_portal_access(
        self, setup, django_capture_on_commit_callbacks
    ):
        admin, student, parent = setup
        client = client_for(admin)
        client.post(url(student), {"photo": image_file()}, format="multipart")
        student.refresh_from_db()
        first = student.photo.name
        with django_capture_on_commit_callbacks(execute=True):
            client.post(
                url(student), {"photo": image_file(size=(400, 400))}, format="multipart"
            )
        student.refresh_from_db()
        assert student.photo.name != first
        assert not student.photo.storage.exists(first)  # old file deleted

        assert client.get(url(student))["Content-Type"] == "image/jpeg"
        portal = client_for(parent).get(f"/api/v1/portal/students/{student.pk}/photo/")
        assert portal.status_code == 200 and "no-store" in portal["Cache-Control"]

        client.delete(url(student))
        assert client.get(url(student)).status_code == 404

    def test_other_parents_cannot_see_photo(self, setup):
        admin, student, _ = setup
        client_for(admin).post(
            url(student), {"photo": image_file()}, format="multipart"
        )
        stranger = User.objects.create_user(phone="+919111111111")
        assert (
            client_for(stranger)
            .get(f"/api/v1/portal/students/{student.pk}/photo/")
            .status_code
            == 404
        )
        assert (
            client_for(stranger)
            .post(url(student), {"photo": image_file()}, format="multipart")
            .status_code
            == 403
        )
