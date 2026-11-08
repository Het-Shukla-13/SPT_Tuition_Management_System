"""
Performance audit: list endpoints must use a CONSTANT number of database
queries, whatever the number of rows ("N+1 query" protection). Each test
measures a page with few rows and with more rows; the counts must match.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
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
from apps.fees.services import create_account, record_payment
from apps.learning.models import (
    DocumentFile,
    Note,
    NoteAssignment,
    TestAssignment,
    TestPaper,
)
from apps.students.models import StudentAccess, StudentProfile, StudentSubject


@pytest.fixture
def base(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    cbse = Board.objects.get(code="CBSE")
    tenth = Standard.objects.get(level=10)
    maths = Subject.objects.get(code="MATH")
    return {
        "admin": User.objects.create_user(
            email="admin@example.com", role=User.Role.ADMIN
        ),
        "parent": User.objects.create_user(phone="+919000000001"),
        "cbse": cbse,
        "tenth": tenth,
        "maths": maths,
        "year": AcademicYear.current(cbse),
        "school": School.objects.create(name="DPS", city="Ahd"),
        "chapter": Chapter.objects.create(
            board=cbse, standard=tenth, subject=maths, number=1, name="C1"
        ),
    }


def _client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def _count(client, url):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200, response.content[:300]
    return len(ctx.captured_queries)


def _add_rows(b, start, n):
    """n students, each with fee account + payment, subject, test & note assignment, parent link."""
    for i in range(start, start + n):
        student = StudentProfile.objects.create(
            admission_number=f"Q-{i}",
            first_name=f"S{i}",
            last_name="X",
            board=b["cbse"],
            standard=b["tenth"],
            school=b["school"],
        )
        StudentAccess.objects.create(user=b["parent"], student=student)
        StudentSubject.objects.create(student=student, subject=b["maths"])
        account = create_account(
            actor=b["admin"],
            student=student,
            academic_year=b["year"],
            agreed_fee=Decimal(1000),
        )
        record_payment(
            actor=b["admin"],
            account=account,
            amount=Decimal(100),
            entry_date=timezone.localdate(),
            method="CASH",
        )
        paper = TestPaper.objects.create(
            title=f"T{i}",
            board=b["cbse"],
            standard=b["tenth"],
            subject=b["maths"],
            academic_year=b["year"],
            max_marks=10,
        )
        paper.chapters.add(b["chapter"])
        DocumentFile.objects.create(
            test_paper=paper,
            kind="PAPER",
            file=f"x{i}.pdf",
            original_name="p.pdf",
            size_bytes=1,
            sha256=f"a{i}",
            version=1,
        )
        DocumentFile.objects.create(
            test_paper=paper,
            kind="ANSWER_KEY",
            file=f"k{i}.pdf",
            original_name="k.pdf",
            size_bytes=1,
            sha256=f"k{i}",
            version=1,
        )
        note = Note.objects.create(
            title=f"N{i}",
            board=b["cbse"],
            standard=b["tenth"],
            subject=b["maths"],
            academic_year=b["year"],
        )
        note.chapters.add(b["chapter"])
        TestAssignment.objects.create(
            student=student,
            test_paper=paper,
            test_starts_at=timezone.now() - timedelta(hours=2),
        )
        NoteAssignment.objects.create(student=student, note=note)


def _assert_constant(b, client, url_fn):
    _add_rows(b, 0, 2)
    small = _count(client, url_fn())
    _add_rows(b, 2, 4)
    large = _count(client, url_fn())
    assert large == small, (
        f"{url_fn()}: {small} queries with 2 rows but {large} with 6 (N+1)"
    )


STAFF_URLS = [
    "/api/v1/admin/students/",
    "/api/v1/admin/users/",
    "/api/v1/admin/fees/accounts/",
    "/api/v1/admin/fees/payments/",
    "/api/v1/staff/tests/",
    "/api/v1/staff/notes/",
    "/api/v1/staff/test-assignments/",
    "/api/v1/staff/note-assignments/",
    "/api/v1/staff/dashboard/",
]


@pytest.mark.django_db
@pytest.mark.parametrize("url", STAFF_URLS)
def test_staff_lists_have_constant_queries(base, url):
    _assert_constant(base, _client(base["admin"]), lambda: url)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "suffix", ["", "{sid}/tests/", "{sid}/notes/", "{sid}/fees/", "{sid}/overview/"]
)
def test_portal_lists_have_constant_queries(base, suffix):
    client = _client(base["parent"])

    def url():
        sid = StudentProfile.objects.order_by("pk").first().pk
        return "/api/v1/portal/students/" + suffix.format(sid=sid)

    if suffix:  # per-student pages: grow that ONE student's rows
        _add_rows(base, 0, 1)
        student = StudentProfile.objects.order_by("pk").first()
        small = _count(client, url())
        for i in range(4):
            paper = TestPaper.objects.create(
                title=f"E{i}",
                board=base["cbse"],
                standard=base["tenth"],
                subject=base["maths"],
                academic_year=base["year"],
            )
            paper.chapters.add(base["chapter"])
            TestAssignment.objects.create(
                student=student,
                test_paper=paper,
                test_starts_at=timezone.now() + timedelta(days=1),
            )
            note = Note.objects.create(
                title=f"EN{i}",
                board=base["cbse"],
                standard=base["tenth"],
                subject=base["maths"],
                academic_year=base["year"],
            )
            note.chapters.add(base["chapter"])
            NoteAssignment.objects.create(student=student, note=note)
        large = _count(client, url())
        assert large == small, f"{url()}: {small} vs {large} queries (N+1)"
    else:
        _assert_constant(base, client, url)
