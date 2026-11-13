"""Enquiries recorded by staff (walk-in / phone / referral), plus the new
medium / school / source fields on both forms."""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.academics.models import Standard
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog
from apps.enquiries.models import AdmissionEnquiry

PUBLIC = "/api/v1/public/enquiries/"
ADMIN = "/api/v1/admin/enquiries/"


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return c


def body(**kw):
    return {
        "parent_name": "Priya Shah",
        "phone": "98765 43210",
        "student_name": "Aarav",
        "standard": Standard.objects.get(level=10).pk,
        **kw,
    }


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.mark.django_db
class TestPublicFormFields:
    def test_keeps_medium_and_school_and_marks_website(self):
        response = APIClient().post(
            PUBLIC,
            body(medium="GUJARATI", school_name="Navrachana School"),
            format="json",
        )
        assert response.status_code == 201
        enquiry = AdmissionEnquiry.objects.get()
        assert enquiry.source == "WEBSITE"
        assert enquiry.medium == "GUJARATI"
        assert enquiry.school_name == "Navrachana School"
        assert enquiry.created_by is None

    def test_rejects_unknown_medium(self):
        response = APIClient().post(PUBLIC, body(medium="FRENCH"), format="json")
        assert response.status_code == 400
        assert not AdmissionEnquiry.objects.exists()


@pytest.mark.django_db
class TestStaffRecordsEnquiry:
    def test_walk_in_is_recorded_as_contacted_without_emailing_admins(
        self, admin, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = client_for(admin).post(
                ADMIN,
                body(medium="ENGLISH", school_name="DPS", notes="Visited with mother"),
                format="json",
            )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["source"] == "WALK_IN"
        assert data["status"] == "CONTACTED"
        assert data["created_by"] == admin.pk
        assert data["handled_by"] == admin.pk
        assert data["notes"] == "Visited with mother"
        assert data["medium"] == "ENGLISH"
        assert data["school_name"] == "DPS"
        assert data["phone"] == "+919876543210"  # normalised like the public form
        assert mail.outbox == []
        assert AuditLog.objects.filter(action="ENQUIRY_CREATED").count() == 1

    def test_source_can_be_phone_but_not_website(self, admin):
        client = client_for(admin)
        phone = client.post(ADMIN, body(source="PHONE"), format="json")
        assert phone.json()["data"]["source"] == "PHONE"
        website = client.post(ADMIN, body(source="WEBSITE"), format="json")
        assert website.status_code == 400
        assert "source" in website.json()["errors"]

    def test_cannot_start_as_admitted(self, admin):
        response = client_for(admin).post(ADMIN, body(status="ACCEPTED"), format="json")
        assert response.status_code == 400

    def test_honeypot_field_is_not_part_of_the_staff_form(self, admin):
        response = client_for(admin).post(
            ADMIN, body(website="spam.example"), format="json"
        )
        assert response.status_code == 201  # ignored, and the enquiry is stored
        assert AdmissionEnquiry.objects.count() == 1

    def test_filter_by_source_and_medium(self, admin):
        client = client_for(admin)
        APIClient().post(PUBLIC, body(medium="HINDI"), format="json")
        client.post(ADMIN, body(medium="ENGLISH"), format="json")
        assert len(client.get(ADMIN, {"source": "WALK_IN"}).json()["data"]) == 1
        assert len(client.get(ADMIN, {"source": "WEBSITE"}).json()["data"]) == 1
        assert len(client.get(ADMIN, {"medium": "HINDI"}).json()["data"]) == 1

    def test_only_admins_record(self):
        teacher = User.objects.create_user(
            email="t@example.com", role=User.Role.TEACHER
        )
        assert client_for(teacher).post(ADMIN, body(), format="json").status_code == 403
        assert APIClient().post(ADMIN, body(), format="json").status_code == 401
