"""Tests & notes: uploads, PDF safety, versions, assignments, answer-key timing, marks, portal access."""

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient

from apps.academics.models import (
    AcademicYear,
    Board,
    Chapter,
    School,
    Standard,
    Subject,
)
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.audit.models import AuditLog
from apps.learning.models import DocumentFile, NoteAssignment, TestAssignment, TestPaper
from apps.students.models import StudentAccess, StudentProfile

TESTS = "/api/v1/staff/tests/"
NOTES = "/api/v1/staff/notes/"
TA = "/api/v1/staff/test-assignments/"
NA = "/api/v1/staff/note-assignments/"


def pdf_bytes(pages=1, marker="") -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": f"doc {marker}"})  # different bytes per marker
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def upload(name="paper.pdf", content=None, marker="a"):
    return SimpleUploadedFile(
        name,
        content if content is not None else pdf_bytes(marker=marker),
        content_type="application/pdf",
    )


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return c


def body(response):
    return b"".join(response.streaming_content)


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def admin(db):
    return User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)


@pytest.fixture
def teacher(db):
    return User.objects.create_user(email="teacher@example.com", role=User.Role.TEACHER)


@pytest.fixture
def ref(db):
    cbse, tenth, maths = (
        Board.objects.get(code="CBSE"),
        Standard.objects.get(level=10),
        Subject.objects.get(code="MATH"),
    )
    return {
        "cbse": cbse,
        "tenth": tenth,
        "maths": maths,
        "school": School.objects.create(name="DPS", city="Ahmedabad"),
        "ch1": Chapter.objects.create(
            board=cbse, standard=tenth, subject=maths, number=1, name="Real Numbers"
        ),
        "other_ch": Chapter.objects.create(
            board=Board.objects.get(code="GSEB"),
            standard=tenth,
            subject=maths,
            number=1,
            name="X",
        ),
    }


def make_student(ref, name="Aarav", phone="+919876543210", status="ACTIVE"):
    student = StudentProfile.objects.create(
        admission_number=f"T-{name}",
        first_name=name,
        last_name="Shah",
        board=ref["cbse"],
        standard=ref["tenth"],
        school=ref["school"],
        status=status,
    )
    parent = User.objects.filter(phone=phone).first() or User.objects.create_user(
        phone=phone
    )
    StudentAccess.objects.create(user=parent, student=student)
    return student, parent


def paper_form(ref, **kw):
    return {
        "title": "Unit test 1",
        "board": ref["cbse"].pk,
        "standard": ref["tenth"].pk,
        "subject": ref["maths"].pk,
        "chapters": [ref["ch1"].pk],
        "max_marks": "25",
        "file": upload(),
        **kw,
    }


def create_paper(user, ref, **kw):
    response = client_for(user).post(TESTS, paper_form(ref, **kw), format="multipart")
    assert response.status_code == 201, response.json()
    return TestPaper.objects.get(pk=response.json()["data"]["id"])


def assign_test(user, paper, students, starts_at=None):
    payload = {"student_ids": [s.pk for s in students]}
    if starts_at is not None:
        payload["test_starts_at"] = starts_at.isoformat()
    return client_for(user).post(f"{TESTS}{paper.pk}/assign/", payload, format="json")


PORTAL = "/api/v1/portal/students/{sid}/"


# ─── uploads & PDF safety ────────────────────────────────────
@pytest.mark.django_db
class TestUploads:
    @pytest.mark.parametrize("who", ["admin", "teacher"])
    def test_staff_upload_test_with_answer_key(self, request, ref, who):
        user = request.getfixturevalue(who)
        paper = create_paper(user, ref, answer_key=upload("key.pdf", marker="key"))

        kinds = set(
            DocumentFile.objects.filter(test_paper=paper).values_list("kind", flat=True)
        )
        assert kinds == {"PAPER", "ANSWER_KEY"}
        assert paper.academic_year == AcademicYear.current(ref["cbse"])  # board default
        assert AuditLog.objects.filter(action="DOCUMENT_UPLOADED").exists()

    def test_portal_user_cannot_upload(self, ref):
        _, parent = make_student(ref)
        response = client_for(parent).post(TESTS, paper_form(ref), format="multipart")
        assert response.status_code == 403

    def test_renamed_non_pdf_rejected(self, admin, ref):
        fake = upload("paper.pdf", content=b"MZ\x90\x00 this is an exe")
        response = client_for(admin).post(
            TESTS, paper_form(ref, file=fake), format="multipart"
        )
        assert response.json()["error_code"] == "INVALID_PDF"
        assert not TestPaper.objects.exists()

    def test_corrupt_pdf_rejected(self, admin, ref):
        broken = upload("paper.pdf", content=b"%PDF-1.7\n garbage garbage")
        response = client_for(admin).post(
            TESTS, paper_form(ref, file=broken), format="multipart"
        )
        assert response.json()["error_code"] == "INVALID_PDF"

    def test_too_large_rejected(self, admin, ref, settings):
        settings.MAX_UPLOAD_SIZE_MB = 0
        response = client_for(admin).post(TESTS, paper_form(ref), format="multipart")
        assert response.json()["error_code"] == "FILE_TOO_LARGE"

    def test_duplicate_pdf_warns_then_confirm(self, admin, ref):
        same = pdf_bytes(marker="same")
        create_paper(admin, ref, file=upload(content=same))
        client = client_for(admin)
        dup = client.post(
            TESTS, paper_form(ref, file=upload(content=same)), format="multipart"
        )
        assert dup.json()["error_code"] == "DUPLICATE_DOCUMENT"
        ok = client.post(
            TESTS,
            paper_form(ref, file=upload(content=same), confirm_duplicate=True),
            format="multipart",
        )
        assert ok.status_code == 201

    def test_chapter_from_other_syllabus_rejected(self, admin, ref):
        response = client_for(admin).post(
            TESTS, paper_form(ref, chapters=[ref["other_ch"].pk]), format="multipart"
        )
        assert response.status_code == 400
        assert "chapters" in response.json()["errors"]

    def test_search_filter_and_archive(self, admin, ref):
        a = create_paper(admin, ref, title="Algebra test")
        create_paper(admin, ref, title="Geometry test", file=upload(marker="g"))
        client = client_for(admin)
        assert [
            t["title"] for t in client.get(TESTS, {"search": "algebra"}).json()["data"]
        ] == ["Algebra test"]
        assert len(client.get(TESTS, {"chapters": ref["ch1"].pk}).json()["data"]) == 2

        client.post(f"{TESTS}{a.pk}/archive/", {"archived": True}, format="json")
        assert [t["title"] for t in client.get(TESTS).json()["data"]] == [
            "Geometry test"
        ]
        archived = client.get(TESTS, {"is_archived": "true"}).json()["data"]
        assert [t["title"] for t in archived] == ["Algebra test"]


# ─── versions ────────────────────────────────────────────────
@pytest.mark.django_db
class TestVersions:
    def test_replace_keeps_old_version_and_students_get_latest(self, admin, ref):
        student, parent = make_student(ref)
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [student])
        new = pdf_bytes(pages=2, marker="v2")

        response = client_for(admin).post(
            f"{TESTS}{paper.pk}/paper/",
            {"file": upload(content=new)},
            format="multipart",
        )

        assert response.json()["data"]["version"] == 2
        assert DocumentFile.objects.filter(test_paper=paper, kind="PAPER").count() == 2
        assignment = TestAssignment.objects.get()
        got = client_for(parent).get(
            PORTAL.format(sid=student.pk) + f"tests/{assignment.pk}/download/"
        )
        assert body(got) == new

        old = client_for(admin).get(f"{TESTS}{paper.pk}/download/", {"version": 1})
        assert body(old) != new


# ─── assignments ─────────────────────────────────────────────
@pytest.mark.django_db
class TestAssignments:
    def test_bulk_assign_reports_partial_failures(self, admin, ref):
        ok, _ = make_student(ref)
        left, _ = make_student(ref, name="Riya", phone="+919000000001", status="LEFT")
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [ok])

        response = assign_test(admin, paper, [ok, left]).json()["data"]
        response2 = (
            client_for(admin)
            .post(
                f"{TESTS}{paper.pk}/assign/", {"student_ids": [999999]}, format="json"
            )
            .json()["data"]
        )

        reasons = {f["student_id"]: f["reason"] for f in response["failed"]}
        assert reasons == {ok.pk: "ALREADY_ASSIGNED", left.pk: "STUDENT_NOT_ACTIVE"}
        assert response2["failed"] == [{"student_id": 999999, "reason": "NOT_FOUND"}]

    def test_archived_item_cannot_be_assigned(self, admin, ref):
        student, _ = make_student(ref)
        paper = create_paper(admin, ref)
        client_for(admin).post(
            f"{TESTS}{paper.pk}/archive/", {"archived": True}, format="json"
        )
        assert (
            assign_test(admin, paper, [student]).json()["error_code"] == "ITEM_ARCHIVED"
        )

    def test_revoke_removes_access_keeps_history_and_reassign_works(self, admin, ref):
        student, parent = make_student(ref)
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [student])
        assignment = TestAssignment.objects.get()
        url = PORTAL.format(sid=student.pk) + f"tests/{assignment.pk}/download/"
        assert client_for(parent).get(url).status_code == 200

        client_for(admin).post(
            f"{TA}revoke/", {"assignment_ids": [assignment.pk]}, format="json"
        )

        assert client_for(parent).get(url).status_code == 404  # old link dead
        assert (
            client_for(parent)
            .get(PORTAL.format(sid=student.pk) + "tests/")
            .json()["data"]
            == []
        )
        assign_test(admin, paper, [student])
        assert (
            TestAssignment.objects.filter(student=student).count() == 2
        )  # both events kept

    def test_teacher_grades_within_max(self, teacher, ref):
        student, parent = make_student(ref)
        paper = create_paper(teacher, ref)
        assign_test(teacher, paper, [student])
        assignment = TestAssignment.objects.get()
        client = client_for(teacher)

        too_high = client.post(
            f"{TA}{assignment.pk}/grade/", {"marks_obtained": "30"}, format="json"
        )
        assert too_high.json()["error_code"] == "MARKS_OUT_OF_RANGE"
        ok = client.post(
            f"{TA}{assignment.pk}/grade/",
            {"marks_obtained": "21.5", "grade_remarks": "Good"},
            format="json",
        )
        assert ok.json()["data"]["marks_obtained"] == "21.50"

        seen = (
            client_for(parent)
            .get(PORTAL.format(sid=student.pk) + "tests/")
            .json()["data"][0]
        )
        assert seen["marks_obtained"] == "21.50" and seen["grade_remarks"] == "Good"

    def test_assignment_list_filters(self, admin, ref):
        student, _ = make_student(ref)
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [student])
        data = client_for(admin).get(TA, {"student": student.pk}).json()["data"]
        assert len(data) == 1 and data[0]["test_title"] == "Unit test 1"


# ─── answer key timing ───────────────────────────────────────
@pytest.mark.django_db
class TestAnswerKey:
    def _setup(self, admin, ref, starts_at, with_key=True):
        student, parent = make_student(ref)
        extra = {"answer_key": upload("key.pdf", marker="key")} if with_key else {}
        paper = create_paper(admin, ref, duration_minutes=60, **extra)
        assign_test(admin, paper, [student], starts_at=starts_at)
        assignment = TestAssignment.objects.get()
        url = (
            PORTAL.format(sid=student.pk)
            + f"tests/{assignment.pk}/download/?kind=ANSWER_KEY"
        )
        return client_for(parent), url, student, assignment

    def test_locked_before_test_ends(self, admin, ref):
        client, url, *_ = self._setup(
            admin, ref, timezone.now() - timedelta(minutes=30)
        )
        response = client.get(url)
        assert response.status_code == 403
        assert response.json()["error_code"] == "ANSWER_KEY_LOCKED"

    def test_unlocked_after_test_ends(self, admin, ref):
        client, url, student, _ = self._setup(
            admin, ref, timezone.now() - timedelta(minutes=61)
        )
        assert client.get(url).status_code == 200
        listing = client.get(PORTAL.format(sid=student.pk) + "tests/").json()["data"][0]
        assert listing["answer_key_available"] is True

    def test_no_test_time_means_never(self, admin, ref):
        client, url, *_ = self._setup(admin, ref, None)
        assert client.get(url).json()["error_code"] == "ANSWER_KEY_LOCKED"

    def test_missing_key_reported(self, admin, ref):
        client, url, *_ = self._setup(
            admin, ref, timezone.now() - timedelta(hours=2), with_key=False
        )
        assert client.get(url).json()["error_code"] == "ANSWER_KEY_UNAVAILABLE"

    def test_staff_can_reschedule(self, admin, ref):
        client, url, _, assignment = self._setup(
            admin, ref, timezone.now() - timedelta(minutes=30)
        )
        later = (timezone.now() - timedelta(hours=3)).isoformat()
        client_for(admin).patch(
            f"{TA}{assignment.pk}/", {"test_starts_at": later}, format="json"
        )
        assert client.get(url).status_code == 200


# ─── portal isolation ────────────────────────────────────────
@pytest.mark.django_db
class TestPortal:
    def test_only_own_students_assignments(self, admin, ref):
        mine, parent = make_student(ref)
        other, _ = make_student(ref, name="Kabir", phone="+919111111111")
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [mine, other])
        others_assignment = TestAssignment.objects.get(student=other)
        client = client_for(parent)

        assert client.get(PORTAL.format(sid=other.pk) + "tests/").status_code == 404
        assert (
            client.get(
                PORTAL.format(sid=mine.pk) + f"tests/{others_assignment.pk}/download/"
            ).status_code
            == 404
        )

    def test_download_headers_and_audit(self, admin, ref):
        student, parent = make_student(ref)
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [student])
        assignment = TestAssignment.objects.get()
        response = client_for(parent).get(
            PORTAL.format(sid=student.pk) + f"tests/{assignment.pk}/download/"
        )
        assert response["Content-Type"] == "application/pdf"
        assert "no-store" in response["Cache-Control"]
        assert AuditLog.objects.filter(action="FILE_ACCESSED", actor=parent).exists()

    def test_inactive_student_sees_no_tests(self, admin, ref):
        student, parent = make_student(ref)
        paper = create_paper(admin, ref)
        assign_test(admin, paper, [student])
        StudentProfile.objects.filter(pk=student.pk).update(status="LEFT")
        assert (
            client_for(parent)
            .get(PORTAL.format(sid=student.pk) + "tests/")
            .json()["data"]
            == []
        )

    def test_staff_cannot_use_portal_and_portal_cannot_use_staff(self, admin, ref):
        student, parent = make_student(ref)
        assert (
            client_for(admin).get(PORTAL.format(sid=student.pk) + "tests/").status_code
            == 403
        )
        assert client_for(parent).get(TESTS).status_code == 403
        assert client_for(parent).get(TA).status_code == 403


# ─── notes ───────────────────────────────────────────────────
@pytest.mark.django_db
class TestNotes:
    def test_upload_assign_search_download_revoke(self, admin, ref):
        student, parent = make_student(ref)
        client = client_for(admin)
        response = client.post(
            NOTES,
            {
                "title": "Real numbers notes",
                "board": ref["cbse"].pk,
                "standard": ref["tenth"].pk,
                "subject": ref["maths"].pk,
                "chapters": [ref["ch1"].pk],
                "file": upload(marker="note"),
            },
            format="multipart",
        )
        assert response.status_code == 201
        note_id = response.json()["data"]["id"]
        client.post(
            f"{NOTES}{note_id}/assign/", {"student_ids": [student.pk]}, format="json"
        )

        portal = client_for(parent)
        base = PORTAL.format(sid=student.pk) + "notes/"
        assert [
            n["title"] for n in portal.get(base, {"search": "real"}).json()["data"]
        ] == ["Real numbers notes"]
        assert portal.get(base, {"chapter": ref["ch1"].pk}).json()["data"]
        assert (
            portal.get(base, {"subject": Subject.objects.get(code="SCI").pk}).json()[
                "data"
            ]
            == []
        )
        assignment = NoteAssignment.objects.get()
        assert portal.get(f"{base}{assignment.pk}/download/").status_code == 200

        client.post(f"{NA}revoke/", {"assignment_ids": [assignment.pk]}, format="json")
        assert (
            portal.get(f"{base}{assignment.pk}/download/").status_code == 404
        )  # revoked via old link
