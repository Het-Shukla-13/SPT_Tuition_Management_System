"""
Dashboards (spec 3 and 9.1). No stored counters: every figure is computed
from the real records each time (spec: "calculated from actual database
records, not manually updated counters").
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from apps.fees.models import LedgerEntry, StudentFeeAccount
from apps.fees.services import with_totals
from apps.learning.models import Note, NoteAssignment, TestAssignment, TestPaper
from apps.students.models import StudentProfile

RECENT = 5
ZERO = Decimal("0.00")


def money(value) -> str | None:
    """Money as an exact string ("26000.00"), like every other API response, never a float."""
    return None if value is None else f"{Decimal(value):.2f}"


# ─────────────────────────────────────────────────────────────
# Staff (admin + teacher)
# ─────────────────────────────────────────────────────────────
def staff_dashboard(*, include_fees: bool, board=None, days: int = 30) -> dict:
    today = timezone.localdate()
    students = StudentProfile.objects.all()
    if board is not None:
        students = students.filter(board=board)

    by_status = dict(students.values_list("status").annotate(n=Count("id")))
    active = students.filter(status=StudentProfile.Status.ACTIVE)
    data = {
        "students": {
            "active": by_status.get("ACTIVE", 0),
            "on_hold": by_status.get("ON_HOLD", 0),
            "left": by_status.get("LEFT", 0),
            "completed": by_status.get("COMPLETED", 0),
            "new_admissions": students.filter(
                admission_date__gte=today - timedelta(days=days)
            ).count(),
            "new_admissions_days": days,
            "active_by_standard": list(
                active.values("standard__name", "standard__level")
                .annotate(count=Count("id"))
                .order_by("standard__level")
            ),
            "recent_admissions": [
                {
                    "id": s.pk,
                    "admission_number": s.admission_number,
                    "name": s.full_name,
                    "standard": s.standard.name,
                    "board": s.board.code,
                    "admission_date": s.admission_date,
                }
                for s in students.select_related("standard", "board").order_by(
                    "-created_at"
                )[:RECENT]
            ],
        },
        "learning": _learning_summary(board),
    }
    if include_fees:
        data["fees"] = _fees_summary(board)
    return data


def _learning_summary(board) -> dict:
    now = timezone.now()
    tests = TestPaper.objects.filter(is_archived=False)
    notes = Note.objects.filter(is_archived=False)
    assignments = TestAssignment.objects.filter(
        revoked_at__isnull=True, student__status="ACTIVE"
    )
    if board is not None:
        tests, notes = tests.filter(board=board), notes.filter(board=board)
        assignments = assignments.filter(student__board=board)
    # Tests that are over but not graded yet ("to grade" list for teachers).
    to_grade = [
        a
        for a in assignments.filter(
            marks_obtained__isnull=True, test_starts_at__lte=now
        ).select_related("test_paper")
        if a.test_ends_at and a.test_ends_at <= now
    ]
    return {
        "upcoming_tests_7_days": assignments.filter(
            test_starts_at__gte=now, test_starts_at__lte=now + timedelta(days=7)
        ).count(),
        "tests_to_grade": len(to_grade),
        "recent_tests": [
            {
                "id": t.pk,
                "title": t.title,
                "subject": t.subject.name,
                "standard": t.standard.name,
                "created_at": t.created_at,
            }
            for t in tests.select_related("subject", "standard").order_by(
                "-created_at"
            )[:RECENT]
        ],
        "recent_notes": [
            {
                "id": n.pk,
                "title": n.title,
                "subject": n.subject.name,
                "standard": n.standard.name,
                "created_at": n.created_at,
            }
            for n in notes.select_related("subject", "standard").order_by(
                "-created_at"
            )[:RECENT]
        ],
    }


def _fees_summary(board) -> dict:
    """Current academic year of each board (or of the chosen board)."""
    accounts = StudentFeeAccount.objects.filter(academic_year__is_current=True)
    if board is not None:
        accounts = accounts.filter(academic_year__board=board)
    rows = list(
        with_totals(accounts).values(
            "pending", "paid", "credit", "status", "is_overdue", "is_ending_soon"
        )
    )
    payments = LedgerEntry.objects.filter(
        entry_type=LedgerEntry.Type.PAYMENT
    ).select_related("account__student", "reversed_by")
    if board is not None:
        payments = payments.filter(account__academic_year__board=board)
    return {
        "scope": "current academic year"
        + (f" ({board})" if board else " of each board"),
        "accounts": len(rows),
        "students_with_pending_fees": sum(1 for r in rows if r["pending"] > 0),
        "students_fully_paid": sum(1 for r in rows if r["status"] == "PAID"),
        "total_outstanding": money(sum((r["pending"] for r in rows), ZERO)),
        "total_collected": money(sum((r["paid"] for r in rows), ZERO)),
        "total_credit": money(sum((r["credit"] for r in rows), ZERO)),
        "overdue": sum(1 for r in rows if r["is_overdue"]),
        "ending_soon_with_dues": sum(1 for r in rows if r["is_ending_soon"]),
        "recent_payments": [
            {
                "id": p.pk,
                "student": p.account.student.full_name,
                "amount": money(p.amount),
                "method": p.method,
                "entry_date": p.entry_date,
                "receipt_number": p.receipt_number,
                "reversed": hasattr(p, "reversed_by"),
            }
            for p in payments.order_by("-entry_date", "-id")[:RECENT]
        ],
    }


# ─────────────────────────────────────────────────────────────
# Portal (parent / student): one linked student's overview
# ─────────────────────────────────────────────────────────────
def student_overview(student: StudentProfile) -> dict:
    now = timezone.now()
    active = student.is_active
    tests = (
        TestAssignment.objects.filter(
            student=student, revoked_at__isnull=True
        ).select_related("test_paper__subject")
        if active
        else TestAssignment.objects.none()
    )
    notes = (
        NoteAssignment.objects.filter(
            student=student, revoked_at__isnull=True
        ).select_related("note__subject")
        if active
        else NoteAssignment.objects.none()
    )
    accounts = list(
        with_totals(
            StudentFeeAccount.objects.filter(student=student).select_related(
                "academic_year"
            )
        ).order_by("-academic_year__start_date")
    )
    current = next(
        (a for a in accounts if a.academic_year.is_current),
        accounts[0] if accounts else None,
    )
    return {
        "student": {
            "id": student.pk,
            "admission_number": student.admission_number,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "standard": student.standard.name,
            "board": student.board.code,
            "school": str(student.school),
            "status": student.status,
            "has_photo": bool(student.photo),
        },
        "upcoming_tests": [
            {
                "assignment_id": a.pk,
                "title": a.test_paper.title,
                "subject": a.test_paper.subject.name,
                "test_starts_at": a.test_starts_at,
            }
            for a in tests.filter(test_starts_at__gte=now).order_by("test_starts_at")[
                :RECENT
            ]
        ],
        "recent_results": [
            {
                "assignment_id": a.pk,
                "title": a.test_paper.title,
                "subject": a.test_paper.subject.name,
                "marks_obtained": money(a.marks_obtained),
                "max_marks": money(a.test_paper.max_marks),
            }
            for a in tests.filter(marks_obtained__isnull=False).order_by("-graded_at")[
                :RECENT
            ]
        ],
        "recent_notes": [
            {
                "assignment_id": n.pk,
                "title": n.note.title,
                "subject": n.note.subject.name,
                "assigned_at": n.assigned_at,
            }
            for n in notes.order_by("-assigned_at")[:RECENT]
        ],
        "fees": None
        if current is None
        else {
            "academic_year": current.academic_year.name,
            "due_date": current.academic_year.end_date,
            "total": money(current.total),
            "paid": money(current.paid),
            "pending": money(current.pending),
            "credit": money(current.credit),
            "status": current.status,
            "is_overdue": current.is_overdue,
            "pending_all_years": money(sum((a.pending for a in accounts), ZERO)),
        },
    }
