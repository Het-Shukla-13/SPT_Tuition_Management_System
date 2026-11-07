import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.academics.models import Standard
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
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
class TestPublicForm:
    def test_submit_stores_and_emails_admins(
        self, admin, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = APIClient().post(PUBLIC, body(), format="json")
        assert response.status_code == 201
        enquiry = AdmissionEnquiry.objects.get()
        assert enquiry.phone == "+919876543210" and enquiry.status == "NEW"
        assert mail.outbox[-1].to == ["admin@example.com"]
        assert not User.objects.filter(
            phone="+919876543210"
        ).exists()  # no login created

    def test_honeypot_pretends_success_stores_nothing(self):
        response = APIClient().post(PUBLIC, body(website="spam.example"), format="json")
        assert response.status_code == 201
        assert not AdmissionEnquiry.objects.exists()

    def test_validation(self):
        response = APIClient().post(PUBLIC, body(phone="12"), format="json")
        assert response.status_code == 400

    def test_throttled(self, settings):
        from apps.common.throttling import ResilientScopedRateThrottle

        rates = {**ResilientScopedRateThrottle.THROTTLE_RATES, "enquiry": "1/hour"}
        from unittest import mock

        with mock.patch.object(ResilientScopedRateThrottle, "THROTTLE_RATES", rates):
            APIClient().post(PUBLIC, body(), format="json")
            assert APIClient().post(PUBLIC, body(), format="json").status_code == 429


@pytest.mark.django_db
class TestAdmin:
    def test_list_filter_and_update(self, admin):
        APIClient().post(PUBLIC, body(), format="json")
        client = client_for(admin)
        data = client.get(ADMIN, {"status": "NEW"}).json()["data"]
        assert len(data) == 1
        response = client.patch(
            f"{ADMIN}{data[0]['id']}/",
            {"status": "CONTACTED", "notes": "Called"},
            format="json",
        )
        assert response.json()["data"]["status"] == "CONTACTED"
        assert response.json()["data"]["handled_by"] == admin.pk

    def test_non_admins_blocked(self):
        portal = User.objects.create_user(phone="+919111111111")
        assert client_for(portal).get(ADMIN).status_code == 403
        assert APIClient().get(ADMIN).status_code == 401
