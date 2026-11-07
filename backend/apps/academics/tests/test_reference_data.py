"""Academic reference data: seeded values, read/write access, uniqueness, deactivation."""

import pytest
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Board, Chapter, Standard, Subject
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens

BASE = "/api/v1/academics/"


def client_for(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def teacher(db):
    return User.objects.create_user(email="teacher@example.com", role=User.Role.TEACHER)


@pytest.fixture
def portal(db):
    return User.objects.create_user(email="parent@example.com")


@pytest.mark.django_db
class TestSeedData:
    def test_seeded_boards_standards_subjects_year(self):
        assert set(Board.objects.values_list("code", flat=True)) == {
            "CBSE",
            "GSEB",
            "ICSE",
        }
        assert list(Standard.objects.values_list("name", flat=True)) == [
            "1st",
            "2nd",
            "3rd",
            "4th",
            "5th",
            "6th",
            "7th",
            "8th",
            "9th",
            "10th",
        ]
        assert set(Subject.objects.values_list("name", flat=True)) == {
            "English",
            "Mathematics",
            "Science",
            "Social Studies",
            "Gujarati",
            "Hindi",
        }
        assert AcademicYear.current().name == "2026-27"


@pytest.mark.django_db
class TestAccess:
    def test_anonymous_cannot_read(self):
        assert APIClient().get(f"{BASE}boards/").status_code == 401

    @pytest.mark.parametrize("who", ["admin", "teacher", "portal"])
    def test_any_logged_in_user_can_read(self, request, who):
        response = client_for(request.getfixturevalue(who)).get(f"{BASE}standards/")
        assert response.status_code == 200
        assert response.json()["meta"]["total_count"] == 10

    @pytest.mark.parametrize("who", ["teacher", "portal"])
    def test_only_admin_can_write(self, request, who):
        client = client_for(request.getfixturevalue(who))
        response = client.post(
            f"{BASE}subjects/", {"name": "Sanskrit", "code": "SAN"}, format="json"
        )
        assert response.status_code == 403
        assert not Subject.objects.filter(code="SAN").exists()

    def test_delete_not_allowed(self, admin):
        board = Board.objects.get(code="CBSE")
        response = client_for(admin).delete(f"{BASE}boards/{board.pk}/")
        assert response.status_code == 405
        assert Board.objects.filter(pk=board.pk).exists()


@pytest.mark.django_db
class TestAdminWrites:
    def test_create_subject(self, admin):
        response = client_for(admin).post(
            f"{BASE}subjects/", {"name": "Sanskrit", "code": "SAN"}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["data"]["name"] == "Sanskrit"

    def test_case_insensitive_duplicates_rejected(self, admin):
        client = client_for(admin)
        r1 = client.post(f"{BASE}boards/", {"name": "x", "code": "cbse"}, format="json")
        r2 = client.post(
            f"{BASE}subjects/", {"name": "MATHEMATICS", "code": "M2"}, format="json"
        )
        assert r1.status_code == r2.status_code == 400
        assert "code" in r1.json()["errors"] and "name" in r2.json()["errors"]

    def test_school_unique_per_city_ignoring_case(self, admin):
        client = client_for(admin)
        body = {"name": "St. Xavier's", "city": "Ahmedabad"}
        assert client.post(f"{BASE}schools/", body, format="json").status_code == 201
        dup = client.post(
            f"{BASE}schools/",
            {"name": "st. xavier's", "city": "AHMEDABAD"},
            format="json",
        )
        assert dup.status_code == 400
        other_city = client.post(
            f"{BASE}schools/", {"name": "St. Xavier's", "city": "Surat"}, format="json"
        )
        assert other_city.status_code == 201

    def test_chapter_number_unique_per_syllabus(self, admin):
        cbse, gseb = Board.objects.get(code="CBSE"), Board.objects.get(code="GSEB")
        tenth, maths = Standard.objects.get(level=10), Subject.objects.get(code="MATH")
        body = {
            "board": cbse.pk,
            "standard": tenth.pk,
            "subject": maths.pk,
            "number": 1,
            "name": "Real Numbers",
        }
        client = client_for(admin)
        assert client.post(f"{BASE}chapters/", body, format="json").status_code == 201
        assert client.post(f"{BASE}chapters/", body, format="json").status_code == 400
        assert (
            client.post(
                f"{BASE}chapters/", {**body, "board": gseb.pk}, format="json"
            ).status_code
            == 201
        )

    def test_chapter_filters(self, admin):
        cbse, tenth = Board.objects.get(code="CBSE"), Standard.objects.get(level=10)
        maths, sci = Subject.objects.get(code="MATH"), Subject.objects.get(code="SCI")
        Chapter.objects.create(
            board=cbse, standard=tenth, subject=maths, number=1, name="A"
        )
        Chapter.objects.create(
            board=cbse, standard=tenth, subject=sci, number=1, name="B"
        )
        data = (
            client_for(admin)
            .get(f"{BASE}chapters/", {"subject": maths.pk})
            .json()["data"]
        )
        assert [c["name"] for c in data] == ["A"]
        assert data[0]["board_code"] == "CBSE"


@pytest.mark.django_db
class TestDeactivation:
    def test_deactivated_hidden_from_non_admins_visible_to_admin(self, admin, portal):
        board = Board.objects.get(code="ICSE")
        client_for(admin).patch(
            f"{BASE}boards/{board.pk}/", {"is_active": False}, format="json"
        )

        portal_codes = [
            b["code"] for b in client_for(portal).get(f"{BASE}boards/").json()["data"]
        ]
        assert "ICSE" not in portal_codes
        assert client_for(portal).get(f"{BASE}boards/{board.pk}/").status_code == 404
        inactive = (
            client_for(admin)
            .get(f"{BASE}boards/", {"is_active": "false"})
            .json()["data"]
        )
        assert [b["code"] for b in inactive] == ["ICSE"]


@pytest.mark.django_db
class TestAcademicYear:
    def test_making_a_year_current_switches_the_old_one_off(self, admin):
        response = client_for(admin).post(
            f"{BASE}academic-years/",
            {
                "name": "2027-28",
                "start_date": "2027-04-01",
                "end_date": "2028-03-31",
                "is_current": True,
            },
            format="json",
        )
        assert response.status_code == 201
        assert AcademicYear.current().name == "2027-28"
        assert AcademicYear.objects.filter(is_current=True).count() == 1

    def test_end_must_be_after_start(self, admin):
        response = client_for(admin).post(
            f"{BASE}academic-years/",
            {"name": "bad", "start_date": "2027-04-01", "end_date": "2027-03-01"},
            format="json",
        )
        assert response.status_code == 400
        assert "end_date" in response.json()["errors"]
