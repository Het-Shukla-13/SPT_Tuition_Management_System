"""
Student business logic. Views only validate input and call these.

Every write runs in a transaction and is audited. Messages (invites) are sent
only after the transaction commits.
"""

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.academics.models import AcademicYear
from apps.accounts.models import User, UserSession
from apps.accounts.services.users import create_login, send_invite
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.students.exceptions import (
    AccessAlreadyGranted,
    AccessNotFound,
    InactiveReference,
    NoCurrentAcademicYear,
    NotAPortalLogin,
    NothingChanged,
    PossibleDuplicateStudent,
)
from apps.students.models import (
    AdmissionSequence,
    StudentAcademicHistory,
    StudentAccess,
    StudentProfile,
    StudentSubject,
)

logger = logging.getLogger(__name__)

PERSONAL_FIELDS = (
    "first_name",
    "last_name",
    "date_of_birth",
    "gender",
    "address",
    "guardian_name",
    "guardian_relation",
    "guardian_phone",
    "guardian_email",
    "remarks",
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _current_year(board) -> AcademicYear:
    """The board's current academic year (each board has its own dates)."""
    year = AcademicYear.current(board)
    if year is None:
        raise NoCurrentAcademicYear(
            f"Set a current academic year for {board} first (Academics → academic years)."
        )
    return year


def _ensure_active(*refs) -> None:
    for ref in refs:
        if ref is not None and not ref.is_active:
            raise InactiveReference(f"'{ref}' is deactivated and can't be used.")


def _ensure_portal_login(user: User) -> None:
    if not user.is_portal_user:
        raise NotAPortalLogin()
    if not user.is_active:
        raise NotAPortalLogin("This login is deactivated.")


def next_admission_number(on_date) -> str:
    """SPT-2026-0001, SPT-2026-0002, ... Row-locked, so never repeats."""
    year = on_date.year
    AdmissionSequence.objects.get_or_create(year=year)
    seq = AdmissionSequence.objects.select_for_update().get(pk=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"{settings.ADMISSION_NUMBER_PREFIX}-{year}-{seq.last_number:04d}"


def find_possible_duplicates(
    *, first_name, last_name, date_of_birth=None, guardian_phone="", exclude_pk=None
):
    """
    Same name AND (same date of birth, or same guardian phone, or no date of
    birth to tell them apart). Two different children may share a name, so
    this is a warning the admin can override, never a hard block.
    """
    candidates = StudentProfile.objects.filter(
        first_name__iexact=first_name, last_name__iexact=last_name
    )
    if date_of_birth:
        # A known, different birth date tells two same-name children apart,
        # unless they also share the guardian's phone.
        same_or_unknown = Q(date_of_birth=date_of_birth) | Q(date_of_birth__isnull=True)
        if guardian_phone:
            same_or_unknown |= Q(guardian_phone=guardian_phone)
        candidates = candidates.filter(same_or_unknown)
    if exclude_pk:
        candidates = candidates.exclude(pk=exclude_pk)
    return list(candidates.select_related("standard")[:10])


def _grant(actor: User, student: StudentProfile, user: User, ip=None) -> StudentAccess:
    _ensure_portal_login(user)
    if StudentAccess.objects.filter(
        user=user, student=student, revoked_at__isnull=True
    ).exists():
        raise AccessAlreadyGranted()
    try:
        with transaction.atomic():
            link = StudentAccess.objects.create(
                user=user, student=student, granted_by=actor
            )
    except IntegrityError:
        raise AccessAlreadyGranted() from None
    record(
        AuditLog.Action.STUDENT_ACCESS_GRANTED,
        actor=actor,
        target=student,
        changes={"user_id": user.pk},
        ip=ip,
    )
    return link


def _send_invites_after_commit(users: list[User], sink: dict) -> None:
    def send():
        for user in users:
            sink[user.pk] = send_invite(user)

    transaction.on_commit(send)


# ─────────────────────────────────────────────────────────────
# Admission
# ─────────────────────────────────────────────────────────────
def admit_student(
    *,
    actor: User,
    profile: dict,
    subjects: list,
    link_users: list[User],
    new_logins: list[dict],
    confirm_duplicate: bool = False,
    ip=None,
) -> tuple[StudentProfile, dict]:
    """
    The admin's "Add new student" form, in one transaction: profile, subjects,
    first academic-history row, access for existing logins, and new logins.
    Returns (student, invites_sent_by_new_user_id).
    """
    invites: dict = {}
    with transaction.atomic():
        year = _current_year(profile["board"])
        _ensure_active(
            profile["board"], profile["standard"], profile["school"], *subjects
        )

        if not confirm_duplicate:
            dups = find_possible_duplicates(
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                date_of_birth=profile.get("date_of_birth"),
                guardian_phone=profile.get("guardian_phone", ""),
            )
            if dups:
                raise PossibleDuplicateStudent(
                    details={
                        "possible_duplicates": [
                            {
                                "id": d.pk,
                                "admission_number": d.admission_number,
                                "name": d.full_name,
                                "standard": d.standard.name,
                                "date_of_birth": d.date_of_birth,
                                "status": d.status,
                            }
                            for d in dups
                        ]
                    }
                )

        admission_date = profile.get("admission_date") or timezone.localdate()
        student = StudentProfile.objects.create(
            **{**profile, "admission_date": admission_date},
            admission_number=next_admission_number(admission_date),
            created_by=actor,
            updated_by=actor,
        )
        StudentAcademicHistory.objects.create(
            student=student,
            academic_year=year,
            board=student.board,
            standard=student.standard,
            school=student.school,
            started_on=admission_date,
            reason=StudentAcademicHistory.Reason.ADMISSION,
            changed_by=actor,
        )
        StudentSubject.objects.bulk_create(
            StudentSubject(
                student=student, subject=s, started_on=admission_date, changed_by=actor
            )
            for s in subjects
        )

        for user in link_users:
            _grant(actor, student, user, ip=ip)
        created = []
        for login in new_logins:
            user = create_login(actor=actor, role=User.Role.PORTAL, ip=ip, **login)
            _grant(actor, student, user, ip=ip)
            created.append(user)

        record(
            AuditLog.Action.STUDENT_ADMITTED,
            actor=actor,
            target=student,
            changes={
                "admission_number": student.admission_number,
                "standard": student.standard.name,
                "board": student.board.code,
                "subjects": [s.code for s in subjects],
                "linked_user_ids": [u.pk for u in link_users] + [u.pk for u in created],
            },
            ip=ip,
        )
        _send_invites_after_commit(created, invites)

    logger.info("Student admitted: id=%s by actor_id=%s", student.pk, actor.pk)
    return student, invites


# ─────────────────────────────────────────────────────────────
# Updates
# ─────────────────────────────────────────────────────────────
@transaction.atomic
def update_student(*, actor: User, student: StudentProfile, changes: dict, ip=None):
    """Personal details and remarks. Board/standard/school go through change_academic."""
    locked = StudentProfile.objects.select_for_update().get(pk=student.pk)
    diff = {}
    for field in PERSONAL_FIELDS:
        if field in changes and changes[field] != getattr(locked, field):
            diff[field] = [getattr(locked, field), changes[field]]
            setattr(locked, field, changes[field])
    if not diff:
        return locked
    locked.updated_by = actor
    locked.save(update_fields=[*diff, "updated_by", "updated_at"])
    record(
        AuditLog.Action.STUDENT_UPDATED,
        actor=actor,
        target=locked,
        changes={k: [str(v[0]), str(v[1])] for k, v in diff.items()},
        ip=ip,
    )
    return locked


@transaction.atomic
def change_academic(
    *, actor: User, student: StudentProfile, board, standard, school, reason, ip=None
) -> StudentProfile:
    """
    Close the current history row and open a new one (spec: a student may
    change standard/school; old history must stay intact).
    """
    locked = StudentProfile.objects.select_for_update().get(pk=student.pk)
    board = board or locked.board
    standard = standard or locked.standard
    school = school or locked.school
    if (board, standard, school) == (locked.board, locked.standard, locked.school):
        raise NothingChanged()
    _ensure_active(board, standard, school)
    year = _current_year(board)
    today = timezone.localdate()

    old = {
        "board": locked.board.code,
        "standard": locked.standard.name,
        "school": str(locked.school),
    }
    StudentAcademicHistory.objects.filter(student=locked, ended_on__isnull=True).update(
        ended_on=today, updated_at=timezone.now()
    )
    StudentAcademicHistory.objects.create(
        student=locked,
        academic_year=year,
        board=board,
        standard=standard,
        school=school,
        started_on=today,
        reason=reason,
        changed_by=actor,
    )
    locked.board, locked.standard, locked.school = board, standard, school
    locked.updated_by = actor
    locked.save(
        update_fields=["board", "standard", "school", "updated_by", "updated_at"]
    )
    record(
        AuditLog.Action.STUDENT_ACADEMIC_CHANGED,
        actor=actor,
        target=locked,
        changes={
            "from": old,
            "to": {
                "board": board.code,
                "standard": standard.name,
                "school": str(school),
            },
            "reason": reason,
        },
        ip=ip,
    )
    return locked


@transaction.atomic
def set_status(*, actor: User, student: StudentProfile, status: str, ip=None):
    """ACTIVE / ON_HOLD / LEFT. Nothing is deleted: fees, tests and history stay."""
    locked = StudentProfile.objects.select_for_update().get(pk=student.pk)
    if locked.status == status:
        return locked
    old = locked.status
    locked.status = status
    locked.left_on = (
        timezone.localdate() if status == StudentProfile.Status.LEFT else None
    )
    locked.updated_by = actor
    locked.save(update_fields=["status", "left_on", "updated_by", "updated_at"])
    record(
        AuditLog.Action.STUDENT_STATUS_CHANGED,
        actor=actor,
        target=locked,
        changes={"status": [old, status]},
        ip=ip,
    )
    return locked


@transaction.atomic
def set_subjects(*, actor: User, student: StudentProfile, subjects: list, ip=None):
    """Replace the current subjects; dropped ones are ended (kept as history)."""
    locked = StudentProfile.objects.select_for_update().get(pk=student.pk)
    _ensure_active(*subjects)
    today = timezone.localdate()
    current = {
        ss.subject_id: ss
        for ss in StudentSubject.objects.filter(student=locked, ended_on__isnull=True)
    }
    wanted = {s.pk: s for s in subjects}
    removed = [sid for sid in current if sid not in wanted]
    added = [s for sid, s in wanted.items() if sid not in current]
    if not removed and not added:
        return locked
    StudentSubject.objects.filter(pk__in=[current[sid].pk for sid in removed]).update(
        ended_on=today
    )
    StudentSubject.objects.bulk_create(
        StudentSubject(student=locked, subject=s, started_on=today, changed_by=actor)
        for s in added
    )
    record(
        AuditLog.Action.STUDENT_SUBJECTS_CHANGED,
        actor=actor,
        target=locked,
        changes={
            "added": [s.code for s in added],
            "removed": [current[sid].subject.code for sid in removed],
        },
        ip=ip,
    )
    return locked


# ─────────────────────────────────────────────────────────────
# Access links
# ─────────────────────────────────────────────────────────────
def grant_access(
    *,
    actor: User,
    student: StudentProfile,
    user: User | None = None,
    new_login: dict | None = None,
    ip=None,
) -> tuple[User, dict | None]:
    """Link an existing PORTAL login, or create one and link it (invite sent after commit)."""
    invites: dict = {}
    with transaction.atomic():
        if new_login:
            user = create_login(actor=actor, role=User.Role.PORTAL, ip=ip, **new_login)
            _grant(actor, student, user, ip=ip)
            _send_invites_after_commit([user], invites)
        else:
            _grant(actor, student, user, ip=ip)
    return user, invites.get(user.pk)


@transaction.atomic
def revoke_access(*, actor: User, student: StudentProfile, user: User, ip=None) -> None:
    link = (
        StudentAccess.objects.select_for_update()
        .filter(user=user, student=student, revoked_at__isnull=True)
        .first()
    )
    if link is None:
        raise AccessNotFound()
    link.revoked_at = timezone.now()
    link.revoked_by = actor
    link.save(update_fields=["revoked_at", "revoked_by"])
    # Devices that had this student selected forget it.
    UserSession.objects.filter(user=user, selected_student=student).update(
        selected_student=None
    )
    record(
        AuditLog.Action.STUDENT_ACCESS_REVOKED,
        actor=actor,
        target=student,
        changes={"user_id": user.pk},
        ip=ip,
    )


# ─────────────────────────────────────────────────────────────
# Portal (parents / students)
# ─────────────────────────────────────────────────────────────
def linked_students(user: User):
    """Students this login can currently see (the "Who's studying?" picker)."""
    return (
        StudentProfile.objects.filter(
            access_links__user=user, access_links__revoked_at__isnull=True
        )
        .select_related("board", "standard", "school")
        .distinct()
    )


def get_linked_student(user: User, pk: int) -> StudentProfile:
    """404 (not 403) for anything not linked: another student's id reveals nothing."""
    student = linked_students(user).filter(pk=pk).first()
    if student is None:
        raise Http404
    return student


def select_student(
    *, user: User, session_id: str | None, student: StudentProfile
) -> None:
    UserSession.objects.filter(user=user, session_id=session_id).update(
        selected_student=student
    )


def selected_student_id(*, user: User, session_id: str | None) -> int | None:
    return (
        UserSession.objects.filter(user=user, session_id=session_id)
        .values_list("selected_student_id", flat=True)
        .first()
    )
