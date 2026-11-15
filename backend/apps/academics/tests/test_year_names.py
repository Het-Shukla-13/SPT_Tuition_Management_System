"""One academic-year name format, so every board's year lines up by name in the fee filters."""

import pytest

from apps.academics.models import Board
from apps.academics.tests.test_reference_data import BASE, admin, client_for

__all__ = ["admin"]  # pytest fixture, imported for use below


def post(admin, name, start="2027-04-01", end="2028-03-31"):
    return client_for(admin).post(
        f"{BASE}academic-years/",
        {
            "board": Board.objects.get(code="CBSE").pk,
            "name": name,
            "start_date": start,
            "end_date": end,
        },
        format="json",
    )


@pytest.mark.django_db
class TestAcademicYearNames:
    def test_yyyy_yy_is_accepted_and_trimmed(self, admin):
        assert post(admin, " 2027-28 ").json()["data"]["name"] == "2027-28"

    @pytest.mark.parametrize(
        "name", ["2027-2028", "27-28", "2027/28", "Year 2027", "bad"]
    )
    def test_other_formats_are_rejected(self, admin, name):
        response = post(admin, name)
        assert response.status_code == 400
        assert "YYYY-YY" in response.json()["errors"]["name"][0]

    def test_the_two_years_must_follow_on(self, admin):
        response = post(admin, "2027-29")
        assert response.status_code == 400
        assert "2027-28" in response.json()["errors"]["name"][0]

    def test_turn_of_the_century(self, admin):
        assert (
            post(admin, "2099-00", start="2099-04-01", end="2100-03-31").status_code
            == 201
        )

    def test_the_name_must_match_the_start_year(self, admin):
        response = post(admin, "2028-29")  # but it starts in 2027
        assert response.status_code == 400
        assert "2027-28" in response.json()["errors"]["name"][0]

    def test_existing_names_still_save_on_edit(self, admin):
        from apps.academics.models import AcademicYear

        year = AcademicYear.current(Board.objects.get(code="CBSE"))
        response = client_for(admin).patch(
            f"{BASE}academic-years/{year.pk}/",
            {"end_date": "2027-04-30"},
            format="json",
        )
        assert response.status_code == 200
