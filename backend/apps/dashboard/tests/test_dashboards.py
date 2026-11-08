from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Board, School, Standard, Subject
from apps.accounts.models import User
from apps.accounts.services.tokens import issue_tokens
from apps.fees.services import create_account, record_payment
from apps.learning.models import TestAssignment, TestPaper
from apps.students.models import StudentAccess, StudentProfile

STAFF = "/api/v1/staff/dashboard/"


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return c


@pytest.fixture
def world(db):
    admin = User.objects.create_user(email="admin@example.com", role=User.Role.ADMIN)
    cbse, gseb = Board.objects.get(code="CBSE"), Board.objects.get(code="GSEB")
    tenth = Standard.objects.get(level=10)
    school = School.objects.create(name="DPS", city="Ahmedabad")
    maths = Subject.objects.get(code="MATH")

    def student(name, board=cbse, status="ACTIVE", days_ago=1):
        return StudentProfile.objects.create(
            admission_number=f"A-{name}",
            first_name=name,
            last_name="Shah",
            board=board,
            standard=tenth,
            school=school,
            status=status,
            admission_date=timezone.localdate() - timedelta(days=days_ago),
        )

    paid, partial, pending = (
        student("Paid"),
        student("Part"),
        student("Pend", board=gseb),
    )
    student("Old", status="LEFT", days_ago=400)
    for s, fee in ((paid, 10000), (partial, 10000), (pending, 20000)):
        account = create_account(
            actor=admin,
            student=s,
            academic_year=AcademicYear.current(s.board),
            agreed_fee=Decimal(fee),
        )
        if s is paid:
            record_payment(
                actor=admin,
                account=account,
                amount=Decimal(10000),
                entry_date=timezone.localdate(),
                method="CASH",
            )
        if s is partial:
            record_payment(
                actor=admin,
                account=account,
                amount=Decimal(4000),
                entry_date=timezone.localdate(),
                method="UPI",
            )

    paper = TestPaper.objects.create(
        title="Unit 1",
        board=cbse,
        standard=tenth,
        subject=maths,
        academic_year=AcademicYear.current(cbse),
        max_marks=25,
        duration_minutes=60,
    )
    TestAssignment.objects.create(
        student=paid,
        test_paper=paper,
        test_starts_at=timezone.now() - timedelta(hours=3),
    )
    TestAssignment.objects.create(
        student=partial,
        test_paper=paper,
        test_starts_at=timezone.now() + timedelta(days=2),
    )
    return {
        "admin": admin,
        "cbse": cbse,
        "paid": paid,
        "partial": partial,
        "pending": pending,
    }


@pytest.mark.django_db
class TestStaffDashboard:
    def test_admin_sees_students_learning_and_fees(self, world):
        data = client_for(world["admin"]).get(STAFF).json()["data"]

        assert data["students"]["active"] == 3 and data["students"]["left"] == 1
        assert data["students"]["new_admissions"] == 3  # the LEFT one was 400 days ago
        assert data["students"]["active_by_standard"] == [
            {"standard__name": "10th", "standard__level": 10, "count": 3}
        ]
        fees = data["fees"]
        assert fees["students_fully_paid"] == 1
        assert fees["students_with_pending_fees"] == 2
        assert fees["total_outstanding"] == "26000.00"  # 6000 + 20000
        assert fees["total_collected"] == "14000.00"
        assert len(fees["recent_payments"]) == 2
        assert data["learning"]["tests_to_grade"] == 1
        assert data["learning"]["upcoming_tests_7_days"] == 1

    def test_board_filter(self, world):
        data = (
            client_for(world["admin"])
            .get(STAFF, {"board": world["cbse"].pk})
            .json()["data"]
        )
        assert data["students"]["active"] == 2
        assert data["fees"]["total_outstanding"] == "6000.00"

    def test_teacher_gets_no_fees(self, world):
        teacher = User.objects.create_user(
            email="t@example.com", role=User.Role.TEACHER
        )
        data = client_for(teacher).get(STAFF).json()["data"]
        assert "fees" not in data and data["students"]["active"] == 3

    def test_portal_and_anonymous_blocked(self, world):
        parent = User.objects.create_user(phone="+919000000009")
        assert client_for(parent).get(STAFF).status_code == 403
        assert APIClient().get(STAFF).status_code == 401

    def test_days_validation(self, world):
        assert client_for(world["admin"]).get(STAFF, {"days": "abc"}).status_code == 400
        assert client_for(world["admin"]).get(STAFF, {"days": "0"}).status_code == 400


@pytest.mark.django_db
class TestPortalOverview:
    def test_overview_for_linked_student(self, world):
        parent = User.objects.create_user(phone="+919000000009")
        StudentAccess.objects.create(user=parent, student=world["partial"])
        url = f"/api/v1/portal/students/{world['partial'].pk}/overview/"

        data = client_for(parent).get(url).json()["data"]

        assert data["student"]["first_name"] == "Part"
        assert [t["title"] for t in data["upcoming_tests"]] == ["Unit 1"]
        assert (
            data["fees"]["pending"] == "6000.00" and data["fees"]["status"] == "PARTIAL"
        )

    def test_unlinked_student_is_404(self, world):
        parent = User.objects.create_user(phone="+919000000009")
        url = f"/api/v1/portal/students/{world['paid'].pk}/overview/"
        assert client_for(parent).get(url).status_code == 404
