"""
Fees (spec part 6). Design: docs/plans/phase-4-fees.md.

- FeeStructure: the standard fee for a standard in a board's academic year.
  Only a suggestion for new admissions; changing it never touches accounts.
- StudentFeeAccount: one per student per academic year.
- LedgerEntry: append-only money records. Never edited or deleted: mistakes
  are fixed with a REVERSAL (of a payment) or an ADJUSTMENT. Balances are
  always computed from the entries, never stored as hand-edited counters.

Sign convention for `amount` (always stored positive, except ADJUSTMENT and
CARRY_OUT which are signed): what the student owes ("due") is
    opening_balance + CHARGE + ADJUSTMENT + CARRY_OUT - PAYMENT + REVERSAL + REFUND
due > 0: pending; due < 0: credit (overpaid).
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.academics.models import AcademicYear, Standard, Subject
from apps.common.models import GlobalTimeStampedModel
from apps.students.models import StudentProfile

MONEY = {"max_digits": 12, "decimal_places": 2}


class FeeStructure(GlobalTimeStampedModel):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="+"
    )
    standard = models.ForeignKey(Standard, on_delete=models.PROTECT, related_name="+")
    total_fee = models.DecimalField(**MONEY)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "fee_structures"
        ordering = ["academic_year__board__code", "standard__level"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "standard"],
                name="fee_structures_one_per_standard_year",
            ),
            models.CheckConstraint(
                condition=Q(total_fee__gte=0), name="fee_structures_fee_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.academic_year} {self.standard}: {self.total_fee}"


class FeeStructureAddOn(models.Model):
    """An optional subject's extra yearly fee (e.g. Gujarati +2000), per fee structure.

    Charged only to students who take that subject.
    """

    structure = models.ForeignKey(
        FeeStructure, on_delete=models.CASCADE, related_name="add_ons"
    )
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField(**MONEY)

    class Meta:
        db_table = "fee_structure_add_ons"
        ordering = ["subject__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "subject"],
                name="fee_structure_add_ons_one_per_subject",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="fee_structure_add_ons_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.structure}: {self.subject} +{self.amount}"


class StudentFeeAccount(GlobalTimeStampedModel):
    student = models.ForeignKey(
        StudentProfile, on_delete=models.PROTECT, related_name="fee_accounts"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="+"
    )
    agreed_fee = models.DecimalField(**MONEY)
    opening_balance = models.DecimalField(
        **MONEY,
        default=0,
        help_text="Carried in at creation: + dues (previous year / before the app), - credit.",
    )
    opening_balance_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "student_fee_accounts"
        ordering = ["-academic_year__start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                name="student_fee_accounts_one_per_year",
            ),
            models.CheckConstraint(
                condition=Q(agreed_fee__gte=0),
                name="student_fee_accounts_fee_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} {self.academic_year}"


class LedgerEntry(models.Model):
    class Type(models.TextChoices):
        CHARGE = "CHARGE", "Agreed fee"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        PAYMENT = "PAYMENT", "Payment"
        REVERSAL = "REVERSAL", "Payment reversed"
        REFUND = "REFUND", "Refund"
        CARRY_OUT = "CARRY_OUT", "Carried forward to next year"

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
        CHEQUE = "CHEQUE", "Cheque"
        OTHER = "OTHER", "Other"

    account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.PROTECT, related_name="entries"
    )
    entry_type = models.CharField(max_length=12, choices=Type.choices, db_index=True)
    amount = models.DecimalField(**MONEY)
    entry_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=15, choices=Method.choices, blank=True)
    reference = models.CharField(
        max_length=100, blank=True, help_text="UPI/transaction/cheque no."
    )
    remarks = models.TextField(blank=True)
    visible_to_student = models.BooleanField(
        default=True, help_text="Whether parents/students see the remarks."
    )
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
        help_text="For REVERSAL: the payment it cancels (a payment can be reversed once).",
    )
    idempotency_key = models.CharField(
        max_length=64, unique=True, null=True, blank=True
    )
    receipt_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="For an optional subject's extra fee: CHARGE adds it, ADJUSTMENT (-) takes it off.",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fee_ledger_entries"
        ordering = ["entry_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(entry_type__in=["ADJUSTMENT", "CARRY_OUT"])
                | Q(amount__gt=0),
                name="fee_ledger_entries_positive_amount",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entry_type} {self.amount} ({self.account_id})"


class ReceiptSequence(models.Model):
    """Per-year counter for receipt numbers (row-locked, never repeats)."""

    year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "receipt_sequences"

    def __str__(self) -> str:
        return f"{self.year}: {self.last_number}"
