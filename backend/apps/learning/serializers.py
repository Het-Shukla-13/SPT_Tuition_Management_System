import datetime

from django.utils import timezone
from rest_framework import serializers

from apps.academics.models import AcademicYear, Board, Chapter
from apps.academics.serializers import YEAR_NAME
from apps.learning.models import (
    DocumentFile,
    Note,
    NoteAssignment,
    Semester,
    TestAssignment,
    TestPaper,
)

ITEM_BASE_FIELDS = [
    "title",
    "description",
    "boards",
    "standard",
    "subject",
    "chapters",
    "semester",
    "academic_year_name",
    "remarks",
]


# ─────────────────────────────────────────────────────────────
# Staff: archive items
# ─────────────────────────────────────────────────────────────
class DocumentFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentFile
        fields = ["id", "kind", "version", "original_name", "size_bytes", "uploaded_at"]


class _ItemReadSerializer(serializers.ModelSerializer):
    board_codes = serializers.SerializerMethodField(
        help_text="Boards it suits; empty = every board."
    )
    standard_name = serializers.CharField(source="standard.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    chapter_names = serializers.SerializerMethodField()

    def get_board_codes(self, obj) -> list[str]:
        return [b.code for b in obj.boards.all()]

    files = serializers.SerializerMethodField(help_text="Current PDF(s).")
    active_assignments = serializers.SerializerMethodField()

    def get_chapter_names(self, obj) -> list[str]:
        # Uses the prefetched boards / chapters__board (no query per row).
        several = len(obj.boards.all()) != 1
        return [
            f"{c.board.code} · {c.number}. {c.name}"
            if several
            else f"{c.number}. {c.name}"
            for c in obj.chapters.all()
        ]

    def get_files(self, obj) -> list[dict]:
        current = getattr(obj, "current_files", None)  # prefetched by list views
        if current is None:
            current = obj.files.filter(is_current=True)
        return DocumentFileSerializer(current, many=True).data

    def get_active_assignments(self, obj) -> int:
        annotated = getattr(
            obj, "active_assignment_count", None
        )  # annotated by list views
        if annotated is not None:
            return annotated
        return obj.assignments.filter(revoked_at__isnull=True).count()


class TestPaperSerializer(_ItemReadSerializer):
    class Meta:
        model = TestPaper
        fields = [
            "id",
            *ITEM_BASE_FIELDS,
            "board_codes",
            "standard_name",
            "subject_name",
            "chapter_names",
            "school",
            "test_date",
            "max_marks",
            "duration_minutes",
            "is_archived",
            "files",
            "active_assignments",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class NoteSerializer(_ItemReadSerializer):
    class Meta:
        model = Note
        fields = [
            "id",
            *ITEM_BASE_FIELDS,
            "board_codes",
            "standard_name",
            "subject_name",
            "chapter_names",
            "is_archived",
            "files",
            "active_assignments",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class _ItemWriteSerializer(serializers.ModelSerializer):
    chapters = serializers.PrimaryKeyRelatedField(
        queryset=Chapter.objects.all(), many=True, required=False
    )
    semester = serializers.ChoiceField(
        choices=Semester.choices, required=False, allow_null=True
    )
    boards = serializers.PrimaryKeyRelatedField(
        queryset=Board.objects.all(),
        many=True,
        required=False,
        help_text="Boards it suits. Leave empty for every board.",
    )
    academic_year_name = serializers.CharField(
        max_length=7,
        required=False,
        help_text='The year by name, e.g. "2026-27". Defaults to the current year.',
    )

    def validate_academic_year_name(self, value):
        value = value.strip()
        match = YEAR_NAME.fullmatch(value)
        if not match or int(match["second"]) != (int(match["first"]) + 1) % 100:
            raise serializers.ValidationError("Use the format YYYY-YY, e.g. 2026-27.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "boards" in attrs:
            boards = list(attrs["boards"])
        elif self.instance is not None:
            boards = list(self.instance.boards.all())
        else:
            boards = []
        if self.instance is None and not attrs.get("academic_year_name"):
            # The first chosen board's current year, else the newest current year.
            years = AcademicYear.objects.filter(is_current=True)
            if boards:
                years = years.filter(board__in=boards)
            current = years.order_by("-start_date").first()
            if current is None:
                raise serializers.ValidationError(
                    {"academic_year_name": ["No current academic year is set yet."]}
                )
            attrs["academic_year_name"] = current.name
        # Chapters must match the standard + subject, and one of the boards.
        standard = attrs.get("standard", getattr(self.instance, "standard", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        board_ids = {b.pk for b in boards}
        for chapter in attrs.get("chapters", []):
            wrong_board = board_ids and chapter.board_id not in board_ids
            if wrong_board or (chapter.standard_id, chapter.subject_id) != (
                getattr(standard, "pk", None),
                getattr(subject, "pk", None),
            ):
                raise serializers.ValidationError(
                    {
                        "chapters": [
                            f"Chapter '{chapter.name}' is from a different board/standard/subject."
                        ]
                    }
                )
        for board in attrs.get("boards", []):
            if not board.is_active:
                raise serializers.ValidationError(
                    {"boards": [f"{board.code} is deactivated."]}
                )
        for ref in ("standard", "subject"):
            value = attrs.get(ref)
            if value is not None and not value.is_active:
                raise serializers.ValidationError({ref: ["This item is deactivated."]})
        return attrs


class TestPaperWriteSerializer(_ItemWriteSerializer):
    class Meta:
        model = TestPaper
        fields = [
            *ITEM_BASE_FIELDS,
            "school",
            "test_date",
            "max_marks",
            "duration_minutes",
        ]
        extra_kwargs = {
            "max_marks": {"min_value": 0},
            "duration_minutes": {"min_value": 1},
        }


class NoteWriteSerializer(_ItemWriteSerializer):
    class Meta:
        model = Note
        fields = ITEM_BASE_FIELDS


class TestPaperCreateSerializer(TestPaperWriteSerializer):
    file = serializers.FileField(write_only=True, help_text="The test paper PDF.")
    answer_key = serializers.FileField(
        write_only=True, required=False, help_text="Optional answer key PDF."
    )
    confirm_duplicate = serializers.BooleanField(write_only=True, default=False)

    class Meta(TestPaperWriteSerializer.Meta):
        fields = [
            *TestPaperWriteSerializer.Meta.fields,
            "file",
            "answer_key",
            "confirm_duplicate",
        ]


class NoteCreateSerializer(NoteWriteSerializer):
    file = serializers.FileField(write_only=True, help_text="The notes PDF.")
    confirm_duplicate = serializers.BooleanField(write_only=True, default=False)

    class Meta(NoteWriteSerializer.Meta):
        fields = [*NoteWriteSerializer.Meta.fields, "file", "confirm_duplicate"]


class ReplaceFileSerializer(serializers.Serializer):
    file = serializers.FileField()
    confirm_duplicate = serializers.BooleanField(default=False)


class ArchiveSerializer(serializers.Serializer):
    archived = serializers.BooleanField()


class BulkArchiveSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=200
    )
    archived = serializers.BooleanField()


# ─────────────────────────────────────────────────────────────
# Staff: assignments
# ─────────────────────────────────────────────────────────────
class _AssignBase(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=500
    )
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


def _start(attrs: dict) -> dict:
    """
    test_date (+ optional test_time) -> test_starts_at + has_start_time.
    Only a date means 8:00 that day, with no fixed end.
    """
    if "test_date" not in attrs and "test_time" not in attrs:
        return attrs
    date, time = attrs.pop("test_date", None), attrs.pop("test_time", None)
    if time is not None and date is None:
        raise serializers.ValidationError({"test_date": ["Choose the date too."]})
    if date is None:
        attrs["test_starts_at"], attrs["has_start_time"] = None, True
    else:
        local = datetime.datetime.combine(date, time or datetime.time(8, 0))
        attrs["test_starts_at"] = timezone.make_aware(local)
        attrs["has_start_time"] = time is not None
    return attrs


class _TestTiming(serializers.Serializer):
    test_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="The test day. Without a time, the paper opens at 8:00 that day.",
    )
    test_time = serializers.TimeField(
        required=False,
        allow_null=True,
        help_text="Start time. The answer key opens after start + duration.",
    )
    duration_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )

    def validate(self, attrs):
        return _start(super().validate(attrs))


class AssignTestSerializer(_TestTiming, _AssignBase):
    pass


class AssignNoteSerializer(_AssignBase):
    pass


class RevokeSerializer(serializers.Serializer):
    assignment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=500
    )


class _StudentRef(serializers.Serializer):
    id = serializers.IntegerField()
    admission_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class TestAssignmentSerializer(serializers.ModelSerializer):
    student = _StudentRef()
    test_title = serializers.CharField(source="test_paper.title")
    max_marks = serializers.DecimalField(
        source="test_paper.max_marks", max_digits=6, decimal_places=2
    )
    test_ends_at = serializers.DateTimeField(allow_null=True)
    visible_from = serializers.DateTimeField()
    is_over = serializers.BooleanField(help_text="Marks can be entered.")
    answer_key_unlocked = serializers.BooleanField()

    class Meta:
        model = TestAssignment
        fields = [
            "id",
            "student",
            "test_paper",
            "test_title",
            "assigned_at",
            "assigned_by",
            "test_starts_at",
            "has_start_time",
            "duration_minutes",
            "visible_from",
            "test_ends_at",
            "is_over",
            "answer_key_unlocked",
            "remarks",
            "max_marks",
            "marks_obtained",
            "grade_remarks",
            "graded_at",
            "revoked_at",
        ]


class NoteAssignmentSerializer(serializers.ModelSerializer):
    student = _StudentRef()
    note_title = serializers.CharField(source="note.title")

    class Meta:
        model = NoteAssignment
        fields = [
            "id",
            "student",
            "note",
            "note_title",
            "assigned_at",
            "assigned_by",
            "remarks",
            "revoked_at",
        ]


class TestAssignmentUpdateSerializer(_TestTiming):
    """Reschedule one student's test: date, optional time, duration, remarks."""

    remarks = serializers.CharField(required=False, allow_blank=True)


class GradeSerializer(serializers.Serializer):
    marks_obtained = serializers.DecimalField(
        max_digits=6, decimal_places=2, allow_null=True
    )
    grade_remarks = serializers.CharField(required=False, allow_blank=True, default="")


# ─────────────────────────────────────────────────────────────
# Portal (parents / students)
# ─────────────────────────────────────────────────────────────
class PortalTestSerializer(serializers.ModelSerializer):
    """One assigned test as the student/parent sees it."""

    title = serializers.CharField(source="test_paper.title")
    description = serializers.CharField(source="test_paper.description")
    subject = serializers.CharField(source="test_paper.subject.name")
    standard = serializers.CharField(source="test_paper.standard.name")
    semester = serializers.IntegerField(source="test_paper.semester")
    chapters = serializers.SerializerMethodField()
    max_marks = serializers.DecimalField(
        source="test_paper.max_marks", max_digits=6, decimal_places=2
    )
    test_ends_at = serializers.DateTimeField(allow_null=True)
    visible_from = serializers.DateTimeField(
        help_text="When the question paper opens (start time, or 8:00 on the date)."
    )
    paper_available = serializers.BooleanField()
    is_over = serializers.BooleanField()
    has_answer_key = serializers.SerializerMethodField()
    answer_key_available = serializers.SerializerMethodField(
        help_text="True once the test is over and an answer key exists."
    )

    class Meta:
        model = TestAssignment
        fields = [
            "id",
            "title",
            "description",
            "subject",
            "standard",
            "semester",
            "chapters",
            "assigned_at",
            "test_starts_at",
            "has_start_time",
            "visible_from",
            "test_ends_at",
            "paper_available",
            "is_over",
            "remarks",
            "max_marks",
            "marks_obtained",
            "grade_remarks",
            "has_answer_key",
            "answer_key_available",
        ]

    def get_chapters(self, obj) -> list[str]:
        return [f"{c.number}. {c.name}" for c in obj.test_paper.chapters.all()]

    def get_has_answer_key(self, obj) -> bool:
        keys = getattr(obj.test_paper, "current_answer_keys", None)  # prefetched
        if keys is not None:
            return bool(keys)
        return obj.test_paper.files.filter(
            kind=DocumentFile.Kind.ANSWER_KEY, is_current=True
        ).exists()

    def get_answer_key_available(self, obj) -> bool:
        return obj.answer_key_unlocked and self.get_has_answer_key(obj)


class PortalNoteSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="note.title")
    description = serializers.CharField(source="note.description")
    subject = serializers.CharField(source="note.subject.name")
    subject_id = serializers.IntegerField(source="note.subject_id")
    standard = serializers.CharField(source="note.standard.name")
    chapters = serializers.SerializerMethodField()

    class Meta:
        model = NoteAssignment
        fields = [
            "id",
            "title",
            "description",
            "subject",
            "subject_id",
            "standard",
            "chapters",
            "assigned_at",
            "remarks",
        ]

    def get_chapters(self, obj) -> list[str]:
        return [f"{c.number}. {c.name}" for c in obj.note.chapters.all()]
