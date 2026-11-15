"""
Tests/notes for several boards (or every board), named academic years, and the
test timing rules: the paper opens at the start (8:00 on the date if no time),
the answer key and marks once the test is over.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics.models import Board
from apps.learning.models import TestAssignment, TestPaper
from apps.learning.tests.test_learning import (
    NOTES,
    PORTAL,
    TA,
    TESTS,
    admin,
    client_for,
    create_paper,
    make_student,
    paper_form,
    ref,
    timing,
    upload,
)

__all__ = ["admin", "ref"]  # pytest fixtures, imported for use below


def gseb():
    return Board.objects.get(code="GSEB")


@pytest.mark.django_db
class TestBoardsAndYearName:
    def test_no_boards_means_every_board(self, admin, ref):
        paper = create_paper(admin, ref, boards=[], chapters=[])
        data = client_for(admin).get(f"{TESTS}{paper.pk}/").json()["data"]
        assert data["board_codes"] == []
        # Listed under every board.
        for board in (ref["cbse"], gseb()):
            listed = client_for(admin).get(TESTS, {"board": board.pk}).json()["data"]
            assert [t["id"] for t in listed] == [paper.pk]

    def test_several_boards_and_their_chapters(self, admin, ref):
        paper = create_paper(
            admin,
            ref,
            boards=[ref["cbse"].pk, gseb().pk],
            chapters=[ref["ch1"].pk, ref["other_ch"].pk],
        )
        data = client_for(admin).get(f"{TESTS}{paper.pk}/").json()["data"]
        assert sorted(data["board_codes"]) == ["CBSE", "GSEB"]
        # With several boards, chapters say which board they're from.
        assert sorted(data["chapter_names"]) == [
            "CBSE · 1. Real Numbers",
            "GSEB · 1. X",
        ]
        icse = Board.objects.get(code="ICSE")
        assert client_for(admin).get(TESTS, {"board": icse.pk}).json()["data"] == []

    def test_chapter_must_belong_to_a_chosen_board(self, admin, ref):
        response = client_for(admin).post(
            TESTS,
            paper_form(ref, boards=[ref["cbse"].pk], chapters=[ref["other_ch"].pk]),
            format="multipart",
        )
        assert response.status_code == 400
        assert "chapters" in response.json()["errors"]

    def test_year_name_defaults_and_is_checked(self, admin, ref):
        paper = create_paper(admin, ref)
        assert paper.academic_year_name == "2026-27"
        bad = client_for(admin).post(
            TESTS, paper_form(ref, academic_year_name="2026-2027"), format="multipart"
        )
        assert bad.status_code == 400
        assert "academic_year_name" in bad.json()["errors"]
        named = create_paper(
            admin, ref, academic_year_name="2025-26", file=upload(marker="b")
        )
        assert named.academic_year_name == "2025-26"
        listed = (
            client_for(admin)
            .get(TESTS, {"academic_year_name": "2025-26"})
            .json()["data"]
        )
        assert [t["id"] for t in listed] == [named.pk]

    def test_editing_the_boards(self, admin, ref):
        paper = create_paper(admin, ref, chapters=[])
        response = client_for(admin).patch(
            f"{TESTS}{paper.pk}/", {"boards": [gseb().pk]}, format="json"
        )
        assert response.json()["data"]["board_codes"] == ["GSEB"]

    def test_notes_too(self, admin, ref):
        response = client_for(admin).post(
            NOTES,
            {
                "title": "Any-board notes",
                "standard": ref["tenth"].pk,
                "subject": ref["maths"].pk,
                "file": upload(marker="note-any"),
            },
            format="multipart",
        )
        assert response.status_code == 201, response.json()
        assert response.json()["data"]["board_codes"] == []


@pytest.mark.django_db
class TestTiming:
    def _paper_url(self, parent, student, assignment, kind="PAPER"):
        return client_for(parent).get(
            PORTAL.format(sid=student.pk)
            + f"tests/{assignment.pk}/download/?kind={kind}"
        )

    def _assign(self, admin, ref, **payload):
        student, parent = make_student(ref)
        paper = create_paper(
            admin, ref, duration_minutes=60, answer_key=upload("key.pdf", marker="key")
        )
        response = client_for(admin).post(
            f"{TESTS}{paper.pk}/assign/",
            {"student_ids": [student.pk], **payload},
            format="json",
        )
        assert response.status_code == 200, response.json()
        return student, parent, TestAssignment.objects.get()

    def test_with_a_time_the_paper_waits_for_the_start(self, admin, ref):
        later = timezone.now() + timedelta(hours=2)
        student, parent, a = self._assign(admin, ref, **timing(later))
        assert a.has_start_time is True
        response = self._paper_url(parent, student, a)
        assert response.status_code == 403
        assert response.json()["error_code"] == "PAPER_LOCKED"
        listing = (
            client_for(parent)
            .get(PORTAL.format(sid=student.pk) + "tests/")
            .json()["data"]
        )
        assert listing[0]["paper_available"] is False  # listed, but locked

    def test_date_only_opens_at_eight_with_its_answer_key(self, admin, ref):
        tomorrow = timezone.localdate() + timedelta(days=1)
        student, parent, a = self._assign(admin, ref, test_date=tomorrow.isoformat())
        assert a.has_start_time is False
        assert timezone.localtime(a.test_starts_at).hour == 8
        assert a.test_ends_at is None
        assert self._paper_url(parent, student, a).status_code == 403

        # Move it to yesterday: 8:00 has passed, so paper and key are both open.
        yesterday = timezone.localdate() - timedelta(days=1)
        client_for(admin).patch(
            f"{TA}{a.pk}/",
            {"test_date": yesterday.isoformat(), "test_time": None},
            format="json",
        )
        assert self._paper_url(parent, student, a).status_code == 200
        assert self._paper_url(parent, student, a, kind="ANSWER_KEY").status_code == 200

    def test_no_date_opens_straight_away(self, admin, ref):
        student, parent, a = self._assign(admin, ref)
        assert self._paper_url(parent, student, a).status_code == 200
        assert self._paper_url(parent, student, a, kind="ANSWER_KEY").status_code == 200

    def test_a_time_needs_a_date(self, admin, ref):
        student, _ = make_student(ref)
        paper = create_paper(admin, ref)
        response = client_for(admin).post(
            f"{TESTS}{paper.pk}/assign/",
            {"student_ids": [student.pk], "test_time": "10:00"},
            format="json",
        )
        assert response.status_code == 400
        assert "test_date" in response.json()["errors"]

    def test_marks_only_once_the_test_is_over(self, admin, ref):
        later = timezone.now() + timedelta(hours=2)
        student, _, a = self._assign(admin, ref, **timing(later))
        url = f"{TA}{a.pk}/grade/"
        early = client_for(admin).post(url, {"marks_obtained": "20"}, format="json")
        assert early.json()["error_code"] == "TEST_NOT_OVER"
        # Reschedule into the past (edit time), then marks are accepted.
        client_for(admin).patch(
            f"{TA}{a.pk}/", timing(timezone.now() - timedelta(hours=3)), format="json"
        )
        assert (
            client_for(admin)
            .post(url, {"marks_obtained": "20"}, format="json")
            .status_code
            == 200
        )
        # Clearing marks is always allowed.
        cleared = client_for(admin).post(url, {"marks_obtained": None}, format="json")
        assert cleared.status_code == 200

    def test_staff_see_the_timing(self, admin, ref):
        tomorrow = timezone.localdate() + timedelta(days=1)
        _, _, a = self._assign(admin, ref, test_date=tomorrow.isoformat())
        row = (
            client_for(admin).get(TA, {"test_paper": a.test_paper_id}).json()["data"][0]
        )
        assert row["has_start_time"] is False
        assert row["is_over"] is False
        assert row["test_ends_at"] is None


@pytest.mark.django_db
def test_bulk_archive_and_unarchive(admin, ref):
    one = create_paper(admin, ref)
    two = create_paper(admin, ref, file=upload(marker="two"))
    client = client_for(admin)
    response = client.post(
        f"{TESTS}bulk-archive/",
        {"ids": [one.pk, two.pk, 999], "archived": True},
        format="json",
    )
    assert response.json()["data"] == {"done": [one.pk, two.pk], "failed": [999]}
    assert TestPaper.objects.filter(is_archived=True).count() == 2
    assert client.get(TESTS).json()["data"] == []
    client.post(
        f"{TESTS}bulk-archive/", {"ids": [one.pk], "archived": False}, format="json"
    )
    assert [t["id"] for t in client.get(TESTS).json()["data"]] == [one.pk]
