"""
Fees business logic (spec 8.6 financial integrity):

- Every money change is a new LedgerEntry inside a transaction that locks the
  fee account row, so two admins working at once can't produce wrong totals.
- A payment sent with an Idempotency-Key is recorded once: retrying the same
  "Save" returns the original entry instead of a duplicate.
- Totals are always computed from entries (SQL aggregates), never stored.
"""

import io
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, Max, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.fees.exceptions import (
    AlreadyReversed,
    FutureDate,
    IdempotencyConflict,
    InvalidAmount,
    NotAPayment,
    NoteRequired,
    RefundTooLarge,
    SubjectFeeAlreadyCharged,
    SubjectFeeNotCharged,
)
from apps.fees.models import (
    FeeStructureAddOn,
    LedgerEntry,
    ReceiptSequence,
    StudentFeeAccount,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
ENDING_SOON_DAYS = 30
T = LedgerEntry.Type


# ─────────────────────────────────────────────────────────────
# Totals (SQL) and status
# ─────────────────────────────────────────────────────────────
def _sum(entry_type):
    return Coalesce(
        Sum("entries__amount", filter=Q(entries__entry_type=entry_type)),
        Value(ZERO),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def with_totals(queryset=None):
    """
    Annotate fee accounts with charges/payments/... and the derived values:
    total (what was owed), paid (net of reversals & refunds), due (+pending / -credit),
    status, and last_payment_date. Usable in filters and ordering.
    """
    queryset = queryset if queryset is not None else StudentFeeAccount.objects.all()
    money = DecimalField(max_digits=14, decimal_places=2)
    today = timezone.localdate()
    qs = (
        queryset.annotate(
            t_charge=_sum(T.CHARGE),
            t_adjust=_sum(T.ADJUSTMENT),
            t_payment=_sum(T.PAYMENT),
            t_reversal=_sum(T.REVERSAL),
            t_refund=_sum(T.REFUND),
            t_carry=_sum(T.CARRY_OUT),
            last_payment_date=Max(
                "entries__entry_date", filter=Q(entries__entry_type=T.PAYMENT)
            ),
        )
        .annotate(
            total=F("opening_balance") + F("t_charge") + F("t_adjust"),
            paid=F("t_payment") - F("t_reversal") - F("t_refund"),
        )
        .annotate(
            due=F("total") + F("t_carry") - F("paid"),
        )
        .annotate(
            pending=Case(
                When(due__gt=0, then=F("due")), default=Value(ZERO), output_field=money
            ),
            credit=Case(
                When(due__lt=0, then=-F("due")), default=Value(ZERO), output_field=money
            ),
            status=Case(
                When(due__lt=0, then=Value("CREDIT")),
                # Balance moved into next year's account at rollover.
                When(Q(due=0) & ~Q(t_carry=0), then=Value("CARRIED_FORWARD")),
                When(due=0, then=Value("PAID")),
                When(paid__gt=0, then=Value("PARTIAL")),
                default=Value("PENDING"),
            ),
            is_overdue=Case(
                When(
                    Q(due__gt=0) & Q(academic_year__end_date__lt=today),
                    then=Value(True),
                ),
                default=Value(False),
            ),
            is_ending_soon=Case(
                When(
                    Q(due__gt=0)
                    & Q(academic_year__end_date__gte=today)
                    & Q(
                        academic_year__end_date__lte=today
                        + timedelta(days=ENDING_SOON_DAYS)
                    ),
                    then=Value(True),
                ),
                default=Value(False),
            ),
        )
    )
    return qs


def account_with_totals(account_id: int) -> StudentFeeAccount:
    return with_totals(
        StudentFeeAccount.objects.select_related("student", "academic_year")
    ).get(pk=account_id)


def net_paid(account: StudentFeeAccount) -> Decimal:
    return account_with_totals(account.pk).paid


def current_due(account: StudentFeeAccount) -> Decimal:
    return account_with_totals(account.pk).due


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _lock(account: StudentFeeAccount) -> StudentFeeAccount:
    return StudentFeeAccount.objects.select_for_update().get(pk=account.pk)


def _positive(amount) -> Decimal:
    if amount is None or amount <= 0:
        raise InvalidAmount()
    return amount


def _not_future(day) -> None:
    if day > timezone.localdate():
        raise FutureDate()


def next_receipt_number(on_date) -> str:
    year = on_date.year
    ReceiptSequence.objects.get_or_create(year=year)
    seq = ReceiptSequence.objects.select_for_update().get(pk=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"RCPT-{year}-{seq.last_number:05d}"


# ─────────────────────────────────────────────────────────────
# Accounts
# ─────────────────────────────────────────────────────────────
def create_account(
    *,
    actor,
    student,
    academic_year,
    agreed_fee,
    opening_balance=ZERO,
    opening_balance_reason="",
    subject_fees=(),
    ip=None,
) -> StudentFeeAccount:
    """
    Call inside the caller's transaction (admission / rollover).
    subject_fees: [(subject, amount)] extra fees for optional subjects, each its own line.
    """
    if agreed_fee is None or agreed_fee < 0:
        raise InvalidAmount("The agreed fee can't be negative.")
    account = StudentFeeAccount.objects.create(
        student=student,
        academic_year=academic_year,
        agreed_fee=agreed_fee,
        opening_balance=opening_balance or ZERO,
        opening_balance_reason=opening_balance_reason,
        created_by=actor,
    )
    if agreed_fee > 0:
        LedgerEntry.objects.create(
            account=account,
            entry_type=T.CHARGE,
            amount=agreed_fee,
            remarks=f"Agreed fee for {academic_year}",
            recorded_by=actor,
        )
    for subject, amount in subject_fees:
        if amount and amount > 0:
            LedgerEntry.objects.create(
                account=account,
                entry_type=T.CHARGE,
                amount=amount,
                subject=subject,
                remarks=f"{subject.name} (optional subject)",
                recorded_by=actor,
            )
    record(
        AuditLog.Action.FEE_ACCOUNT_CREATED,
        actor=actor,
        target=account,
        changes={
            "agreed_fee": str(agreed_fee),
            "opening_balance": str(opening_balance or ZERO),
            "subject_fees": {s.code: str(a) for s, a in subject_fees if a},
        },
        ip=ip,
    )
    return account


def structure_subject_fees(academic_year, standard, subjects) -> list[tuple]:
    """[(subject, amount)] for the given subjects that have an extra fee this year."""
    ids = [s.pk for s in subjects]
    add_ons = FeeStructureAddOn.objects.filter(
        structure__academic_year=academic_year,
        structure__standard=standard,
        structure__is_active=True,
        subject_id__in=ids,
    ).select_related("subject")
    return [(a.subject, a.amount) for a in add_ons]


def subject_fee_on_account(account, subject) -> Decimal:
    """What's currently charged for this optional subject (its lines added up)."""
    total = account.entries.filter(subject=subject).aggregate(s=Sum("amount"))["s"]
    return total or ZERO


@transaction.atomic
def change_subject_fee(
    *, actor, account, subject, action: str, amount=None, reason: str = "", ip=None
) -> LedgerEntry:
    """
    ADD an optional subject's extra fee (a CHARGE line), or REMOVE it (a minus
    ADJUSTMENT for what's charged). Used when a student starts / drops the subject.
    """
    locked = _lock(account)
    charged = subject_fee_on_account(locked, subject)
    if action == "ADD":
        if charged > 0:
            raise SubjectFeeAlreadyCharged()
        amount = _positive(amount)
        entry = LedgerEntry.objects.create(
            account=locked,
            entry_type=T.CHARGE,
            amount=amount,
            subject=subject,
            remarks=reason.strip() or f"{subject.name} (optional subject)",
            recorded_by=actor,
        )
    else:
        if charged <= 0:
            raise SubjectFeeNotCharged()
        amount = charged if amount is None else _positive(amount)
        if amount > charged:
            raise InvalidAmount("That's more than this subject's fee on the account.")
        entry = LedgerEntry.objects.create(
            account=locked,
            entry_type=T.ADJUSTMENT,
            amount=-amount,
            subject=subject,
            remarks=reason.strip() or f"{subject.name} dropped",
            recorded_by=actor,
        )
    record(
        AuditLog.Action.FEE_ADJUSTED,
        actor=actor,
        target=locked,
        changes={"subject": subject.code, "action": action, "amount": str(amount)},
        ip=ip,
    )
    return entry


@transaction.atomic
def change_agreed_fee(
    *, actor, account, new_fee, reason: str, ip=None
) -> LedgerEntry | None:
    """Spec 8.6 scenario C: an auditable adjustment, never an overwrite."""
    locked = _lock(account)
    if new_fee < 0:
        raise InvalidAmount("The agreed fee can't be negative.")
    difference = new_fee - locked.agreed_fee
    if difference == 0:
        return None
    entry = LedgerEntry.objects.create(
        account=locked,
        entry_type=T.ADJUSTMENT,
        amount=difference,
        remarks=f"Agreed fee changed from {locked.agreed_fee} to {new_fee}: {reason}",
        recorded_by=actor,
    )
    old = locked.agreed_fee
    locked.agreed_fee = new_fee
    locked.save(update_fields=["agreed_fee", "updated_at"])
    record(
        AuditLog.Action.FEE_ADJUSTED,
        actor=actor,
        target=locked,
        changes={"agreed_fee": [str(old), str(new_fee)], "reason": reason},
        ip=ip,
    )
    return entry


# ─────────────────────────────────────────────────────────────
# Money entries
# ─────────────────────────────────────────────────────────────
def record_payment(
    *,
    actor,
    account,
    amount,
    entry_date,
    method,
    reference="",
    remarks="",
    visible_to_student=True,
    idempotency_key: str | None = None,
    ip=None,
) -> tuple[LedgerEntry, bool]:
    """Returns (entry, created). A repeated idempotency key returns the original entry."""
    if idempotency_key:
        existing = LedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.account_id != account.pk or existing.entry_type != T.PAYMENT:
                raise IdempotencyConflict()
            return existing, False
    _positive(amount)
    _not_future(entry_date)
    if method == LedgerEntry.Method.OTHER and not remarks.strip():
        raise NoteRequired(
            "Describe the payment method in remarks when choosing OTHER."
        )
    try:
        with transaction.atomic():
            locked = _lock(account)
            entry = LedgerEntry.objects.create(
                account=locked,
                entry_type=T.PAYMENT,
                amount=amount,
                entry_date=entry_date,
                method=method,
                reference=reference,
                remarks=remarks,
                visible_to_student=visible_to_student,
                idempotency_key=idempotency_key or None,
                receipt_number=next_receipt_number(entry_date),
                recorded_by=actor,
            )
            record(
                AuditLog.Action.FEE_PAYMENT_RECORDED,
                actor=actor,
                target=entry,
                changes={"amount": str(amount), "method": method, "account": locked.pk},
                ip=ip,
            )
    except IntegrityError:
        # A simultaneous retry with the same key won the race.
        existing = LedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
        if existing is None:
            raise
        return existing, False
    return entry, True


@transaction.atomic
def reverse_payment(*, actor, entry: LedgerEntry, reason: str, ip=None) -> LedgerEntry:
    """Spec 8.6 scenario B: cancel a wrong payment; the original stays in history."""
    locked_account = _lock(entry.account)
    entry = LedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.entry_type != T.PAYMENT:
        raise NotAPayment()
    if LedgerEntry.objects.filter(reverses=entry).exists():
        raise AlreadyReversed()
    if not reason.strip():
        raise NoteRequired("Give a reason for the reversal.")
    reversal = LedgerEntry.objects.create(
        account=locked_account,
        entry_type=T.REVERSAL,
        amount=entry.amount,
        reverses=entry,
        remarks=reason,
        recorded_by=actor,
    )
    record(
        AuditLog.Action.FEE_PAYMENT_REVERSED,
        actor=actor,
        target=entry,
        changes={"amount": str(entry.amount), "reason": reason},
        ip=ip,
    )
    return reversal


@transaction.atomic
def add_adjustment(
    *, actor, account, amount, reason: str, visible_to_student=True, ip=None
) -> LedgerEntry:
    """+ adds to what's owed (e.g. extra charge), - reduces it (e.g. concession)."""
    if amount is None or amount == 0:
        raise InvalidAmount("An adjustment can't be zero.")
    if not reason.strip():
        raise NoteRequired("Give a reason for the adjustment.")
    locked = _lock(account)
    entry = LedgerEntry.objects.create(
        account=locked,
        entry_type=T.ADJUSTMENT,
        amount=amount,
        remarks=reason,
        visible_to_student=visible_to_student,
        recorded_by=actor,
    )
    record(
        AuditLog.Action.FEE_ADJUSTED,
        actor=actor,
        target=locked,
        changes={"amount": str(amount), "reason": reason},
        ip=ip,
    )
    return entry


@transaction.atomic
def record_refund(
    *, actor, account, amount, entry_date, method, reference="", reason="", ip=None
) -> LedgerEntry:
    """Spec 8.6 scenario D: money given back, recorded separately."""
    _positive(amount)
    _not_future(entry_date)
    if not reason.strip():
        raise NoteRequired("Give a reason for the refund.")
    locked = _lock(account)
    if amount > net_paid(locked):
        raise RefundTooLarge()
    entry = LedgerEntry.objects.create(
        account=locked,
        entry_type=T.REFUND,
        amount=amount,
        entry_date=entry_date,
        method=method,
        reference=reference,
        remarks=reason,
        recorded_by=actor,
    )
    record(
        AuditLog.Action.FEE_REFUNDED,
        actor=actor,
        target=locked,
        changes={"amount": str(amount), "reason": reason},
        ip=ip,
    )
    return entry


def carry_forward(*, actor, old_account: StudentFeeAccount) -> Decimal:
    """
    Close an old year's balance (dues or credit) so it can be opened in the
    new year's account. Call inside the rollover transaction. Returns the
    amount carried (+ dues / - credit).
    """
    locked = _lock(old_account)
    due = current_due(locked)
    if due != 0:
        LedgerEntry.objects.create(
            account=locked,
            entry_type=T.CARRY_OUT,
            amount=-due,
            remarks="Balance carried forward to the next academic year",
            recorded_by=actor,
        )
    return due


# ─────────────────────────────────────────────────────────────
# Receipt PDF
# ─────────────────────────────────────────────────────────────
def receipt_pdf(entry: LedgerEntry) -> bytes:
    from django.conf import settings
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    account = entry.account
    student = account.student
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A5)
    width, height = A5
    y = height - 20 * mm

    def line(text, size=10, bold=False, gap=7):
        nonlocal y
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        pdf.drawString(15 * mm, y, text)
        y -= gap * mm

    line(settings.INSTITUTE_NAME, size=14, bold=True, gap=9)
    line("Fee receipt", size=12, bold=True, gap=10)
    reversed_ = LedgerEntry.objects.filter(reverses=entry).exists()
    rows = [
        ("Receipt no.", entry.receipt_number or "-"),
        ("Date", entry.entry_date.strftime("%d %b %Y")),
        ("Student", f"{student.full_name} ({student.admission_number})"),
        ("Standard / board", f"{student.standard} / {student.board}"),
        ("Academic year", str(account.academic_year)),
        ("Amount", f"Rs. {entry.amount:,.2f}"),
        ("Method", entry.get_method_display()),
        ("Reference", entry.reference or "-"),
    ]
    for label, value in rows:
        line(f"{label}:  {value}")
    if reversed_:
        line("THIS PAYMENT WAS REVERSED", size=12, bold=True)
    y -= 4 * mm
    line("Computer-generated receipt. No signature required.", size=8)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
