"""
Academic reference data, managed by admins (spec section 12: Board, Standard,
Subject, Chapter; plus School and AcademicYear, which students, tests, notes
and fees all refer to).

Rules:
- Rows are deactivated (`is_active=False`), never deleted while anything
  refers to them: every foreign key to these tables uses PROTECT.
- Names/codes are unique ignoring case, so "cbse" can't duplicate "CBSE".
"""

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.common.models import GlobalTimeStampedModel


class ReferenceModel(GlobalTimeStampedModel):
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class Board(ReferenceModel):
    name = models.CharField(
        max_length=150, help_text="e.g. Central Board of Secondary Education"
    )
    code = models.CharField(max_length=20, help_text="Short name, e.g. CBSE")

    class Meta:
        db_table = "boards"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(Lower("code"), name="boards_code_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.code


class Standard(ReferenceModel):
    name = models.CharField(max_length=30, help_text='e.g. "10th"')
    level = models.PositiveSmallIntegerField(
        unique=True, help_text="Numeric grade used for sorting and promotion, e.g. 10."
    )

    class Meta:
        db_table = "standards"
        ordering = ["level"]

    def __str__(self) -> str:
        return self.name


class Subject(ReferenceModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, help_text="Short code, e.g. MATH")

    class Meta:
        db_table = "subjects"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="subjects_name_ci_unique"),
            models.UniqueConstraint(Lower("code"), name="subjects_code_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.name


class Chapter(ReferenceModel):
    """
    A chapter belongs to a board + standard + subject: "Chapter 3, Maths" is
    different for CBSE 10th and GSEB 10th. Tests and notes will be tagged with it.
    """

    board = models.ForeignKey(Board, on_delete=models.PROTECT, related_name="chapters")
    standard = models.ForeignKey(
        Standard, on_delete=models.PROTECT, related_name="chapters"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="chapters"
    )
    number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=200)

    class Meta:
        db_table = "chapters"
        ordering = ["board__code", "standard__level", "subject__name", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "standard", "subject", "number"],
                name="chapters_unique_number_per_syllabus",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.board} {self.standard} {self.subject} - {self.number}. {self.name}"
        )


class School(ReferenceModel):
    """A list (not free text) so "St. Xavier's" can't become three different schools."""

    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    board = models.ForeignKey(
        Board,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schools",
        help_text="Main board, if the school follows one.",
    )

    class Meta:
        db_table = "schools"
        ordering = ["name", "city"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), Lower("city"), name="schools_name_city_ci_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name}, {self.city}"


class AcademicYear(ReferenceModel):
    name = models.CharField(max_length=20, unique=True, help_text='e.g. "2026-27"')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        db_table = "academic_years"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_current"],
                condition=Q(is_current=True),
                name="academic_years_single_current",
            ),
            models.CheckConstraint(
                condition=Q(end_date__gt=models.F("start_date")),
                name="academic_years_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def current(cls) -> "AcademicYear | None":
        return cls.objects.filter(is_current=True).first()
