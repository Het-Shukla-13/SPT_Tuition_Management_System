"""
Year-end rollover, per board (design D in phase-4-fees.md).

preview(): every ACTIVE student of the board with a suggested action:
  PROMOTE (next standard), REPEAT, LEAVE, COMPLETE (already in the last standard taught).
apply(): per student, in its own transaction:
  - closes the current academic-history row and (PROMOTE/REPEAT) opens one in the new year,
  - LEAVE -> status LEFT; COMPLETE -> status COMPLETED (old dues stay on the old account),
  - PROMOTE/REPEAT -> carries the old balance (dues or credit) into a new fee account.
Returns which students succeeded and which failed (and why).
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.academics.models import AcademicYear, Standard
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.common.exceptions import AppException
from apps.fees.exceptions import AlreadyRolledOver, FeeRequired
from apps.fees.models import FeeStructure, StudentFeeAccount
from apps.fees.services import carry_forward, create_account, current_due
from apps.students.models import StudentAcademicHistory, StudentProfile

PROMOTE, REPEAT, LEAVE, COMPLETE = "PROMOTE", "REPEAT", "LEAVE", "COMPLETE"
ACTIONS = (PROMOTE, REPEAT, LEAVE, COMPLETE)


class WrongBoardYear(AppException):
    default_detail = "That academic year belongs to a different board."
    default_code = "WRONG_BOARD_YEAR"


class NotEligible(AppException):
    default_detail = "Not an active student of this board."
    default_code = "NOT_ELIGIBLE"


class NoNextStandard(AppException):
    default_detail = "There is no next standard to promote to; use COMPLETE."
    default_code = "NO_NEXT_STANDARD"


def _next_standard(standard: Standard) -> Standard | None:
    return (
        Standard.objects.filter(level__gt=standard.level, is_active=True)
        .order_by("level")
        .first()
    )


def _suggested_fee(year: AcademicYear, standard: Standard | None) -> Decimal | None:
    if standard is None:
        return None
    structure = FeeStructure.objects.filter(
        academic_year=year, standard=standard, is_active=True
    ).first()
    return structure.total_fee if structure else None


def _latest_account(student) -> StudentFeeAccount | None:
    return student.fee_accounts.order_by("-academic_year__start_date").first()


def _check_year(board, to_year: AcademicYear) -> None:
    if to_year.board_id != board.pk:
        raise WrongBoardYear()


def preview(*, board, to_year: AcademicYear) -> list[dict]:
    _check_year(board, to_year)
    rows = []
    students = StudentProfile.objects.filter(
        board=board, status=StudentProfile.Status.ACTIVE
    ).select_related("standard")
    for student in students.order_by("standard__level", "first_name"):
        next_std = _next_standard(student.standard)
        action = PROMOTE if next_std else COMPLETE
        old = _latest_account(student)
        rows.append(
            {
                "student_id": student.pk,
                "admission_number": student.admission_number,
                "name": student.full_name,
                "from_standard": student.standard.name,
                "suggested_action": action,
                "to_standard": next_std.name if next_std else None,
                "suggested_agreed_fee": _suggested_fee(to_year, next_std),
                "balance_to_carry": current_due(old) if old else Decimal("0.00"),
                "already_rolled_over": StudentFeeAccount.objects.filter(
                    student=student, academic_year=to_year
                ).exists(),
            }
        )
    return rows


def apply(
    *,
    actor,
    board,
    to_year: AcademicYear,
    items: list[dict],
    make_current: bool = True,
    ip=None,
) -> dict:
    """items: [{student_id, action, agreed_fee?}]"""
    _check_year(board, to_year)
    if make_current:
        with transaction.atomic():
            AcademicYear.objects.select_for_update().filter(
                board=board, is_current=True
            ).exclude(pk=to_year.pk).update(is_current=False)
            AcademicYear.objects.filter(pk=to_year.pk).update(is_current=True)

    result = {"done": [], "failed": []}
    for item in items:
        sid = item["student_id"]
        try:
            with transaction.atomic():
                outcome = _apply_one(
                    actor=actor, board=board, to_year=to_year, item=item, ip=ip
                )
            result["done"].append({"student_id": sid, **outcome})
        except AppException as exc:
            result["failed"].append(
                {
                    "student_id": sid,
                    "reason": exc.default_code,
                    "message": str(exc.detail),
                }
            )
    return result


def _apply_one(*, actor, board, to_year, item, ip) -> dict:
    student = (
        StudentProfile.objects.select_for_update()
        .select_related("standard", "school")
        .filter(pk=item["student_id"], board=board, status=StudentProfile.Status.ACTIVE)
        .first()
    )
    if student is None:
        raise NotEligible()
    if StudentFeeAccount.objects.filter(
        student=student, academic_year=to_year
    ).exists():
        raise AlreadyRolledOver()

    action = item["action"]
    today = timezone.localdate()
    StudentAcademicHistory.objects.filter(
        student=student, ended_on__isnull=True
    ).update(ended_on=today)

    if action in (LEAVE, COMPLETE):
        student.status = (
            StudentProfile.Status.LEFT
            if action == LEAVE
            else StudentProfile.Status.COMPLETED
        )
        student.left_on = today
        student.updated_by = actor
        student.save(update_fields=["status", "left_on", "updated_by", "updated_at"])
        record(
            AuditLog.Action.ROLLOVER_APPLIED,
            actor=actor,
            target=student,
            changes={"action": action, "to_year": str(to_year)},
            ip=ip,
        )
        return {"action": action, "status": student.status}

    new_standard = student.standard
    if action == PROMOTE:
        new_standard = _next_standard(student.standard)
        if new_standard is None:
            raise NoNextStandard()
    agreed_fee = item.get("agreed_fee")
    if agreed_fee is None:
        agreed_fee = _suggested_fee(to_year, new_standard)
    if agreed_fee is None:
        raise FeeRequired()

    old = _latest_account(student)
    carried = carry_forward(actor=actor, old_account=old) if old else Decimal("0.00")
    StudentAcademicHistory.objects.create(
        student=student,
        academic_year=to_year,
        board=student.board,
        standard=new_standard,
        school=student.school,
        started_on=today,
        reason=StudentAcademicHistory.Reason.PROMOTION
        if action == PROMOTE
        else StudentAcademicHistory.Reason.REPEAT,
        changed_by=actor,
    )
    student.standard = new_standard
    student.updated_by = actor
    student.save(update_fields=["standard", "updated_by", "updated_at"])
    account = create_account(
        actor=actor,
        student=student,
        academic_year=to_year,
        agreed_fee=agreed_fee,
        opening_balance=carried,
        opening_balance_reason="Carried forward from previous year" if carried else "",
        ip=ip,
    )
    record(
        AuditLog.Action.ROLLOVER_APPLIED,
        actor=actor,
        target=student,
        changes={
            "action": action,
            "to_year": str(to_year),
            "standard": new_standard.name,
            "carried": str(carried),
        },
        ip=ip,
    )
    return {
        "action": action,
        "standard": new_standard.name,
        "fee_account_id": account.pk,
        "carried": carried,
    }
