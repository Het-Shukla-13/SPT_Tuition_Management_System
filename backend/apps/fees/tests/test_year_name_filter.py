"""Fee lists filter by year name across boards (e.g. every board's 2026-27)."""

import datetime

import pytest

from apps.academics.models import AcademicYear, Board
from apps.fees.models import FeeStructure
from apps.fees.tests.test_fees import ACC, STRUCT, admin, admit, client_for, refs

__all__ = ["admin", "refs"]  # pytest fixtures, imported for use below


@pytest.mark.django_db
def test_year_name_works_with_or_without_a_board(admin, refs):
    gseb = Board.objects.get(code="GSEB")
    gseb_year = AcademicYear.current(gseb)
    cbse_year = AcademicYear.current(refs["cbse"])
    assert gseb_year.name == cbse_year.name  # both boards have a "2026-27"
    older = AcademicYear.objects.create(
        board=refs["cbse"],
        name="2025-26",
        start_date=datetime.date(2025, 4, 1),
        end_date=datetime.date(2026, 3, 31),
    )
    for year in (cbse_year, gseb_year, older):
        FeeStructure.objects.create(
            academic_year=year, standard=refs["tenth"], total_fee=20000
        )
    admit(admin, refs, agreed_fee="20000")
    client = client_for(admin)

    every_board = client.get(STRUCT, {"academic_year__name": cbse_year.name}).json()[
        "data"
    ]
    assert {s["board_code"] for s in every_board} == {"CBSE", "GSEB"}
    one_board = client.get(
        STRUCT, {"academic_year__name": cbse_year.name, "academic_year__board": gseb.pk}
    ).json()["data"]
    assert [s["board_code"] for s in one_board] == ["GSEB"]

    accounts = client.get(ACC, {"academic_year__name": cbse_year.name}).json()["data"]
    assert len(accounts) == 1
    assert client.get(ACC, {"academic_year__name": "2025-26"}).json()["data"] == []
