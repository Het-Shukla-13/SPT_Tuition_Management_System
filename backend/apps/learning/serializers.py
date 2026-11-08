from rest_framework import serializers

from apps.academics.models import AcademicYear, Chapter
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
    "board",
    "standard",
    "subject",
    "chapters",
    "semester",
    "academic_year",
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
    board_code = serializers.CharField(source="board.code", read_only=True)
    standard_name = serializers.CharField(source="standard.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    chapter_names = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField(help_text="Current PDF(s).")
    active_assignments = serializers.SerializerMethodField()

    def get_chapter_names(self, obj) -> list[str]:
        return [f"{c.number}. {c.name}" for c in obj.chapters.all()]

    def get_files(self, obj) -> list[dict]:
        return DocumentFileSerializer(obj.files.filter(is_current=True), many=True).data

    def get_active_assignments(self, obj) -> int:
        return obj.assignments.filter(revoked_at__isnull=True).count()


class TestPaperSerializer(_ItemReadSerializer):
    class Meta:
        model = TestPaper
        fields = [
            "id",
            *ITEM_BASE_FIELDS,
            "board_code",
            "standard_name",
            "subject_name",
            "academic_year_name",
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
            "board_code",
            "standard_name",
            "subject_name",
            "academic_year_name",
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
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.all(),
        required=False,
        help_text="Defaults to the board's current academic year.",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        board = attrs.get("board", getattr(self.instance, "board", None))
        if (
            self.instance is None
            and not attrs.get("academic_year")
            and board is not None
        ):
            current = AcademicYear.current(board)
            if current is None:
                raise serializers.ValidationError(
                    {"academic_year": [f"No current academic year is set for {board}."]}
                )
            attrs["academic_year"] = current
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        if year is not None and board is not None and year.board_id != board.pk:
            raise serializers.ValidationError(
                {"academic_year": ["This academic year belongs to a different board."]}
            )
        # Chapters must belong to the item's board + standard + subject.
        standard = attrs.get("standard", getattr(self.instance, "standard", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        for chapter in attrs.get("chapters", []):
            if (chapter.board_id, chapter.standard_id, chapter.subject_id) != (
                getattr(board, "pk", None),
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
        for ref in ("board", "standard", "subject"):
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


# ─────────────────────────────────────────────────────────────
# Staff: assignments
# ─────────────────────────────────────────────────────────────
class _AssignBase(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=500
    )
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class AssignTestSerializer(_AssignBase):
    test_starts_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="When the test starts. The answer key unlocks for students after start + duration.",
    )
    duration_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )


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
    test_ends_at = serializers.DateTimeField()
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
            "duration_minutes",
            "test_ends_at",
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


class TestAssignmentUpdateSerializer(serializers.Serializer):
    test_starts_at = serializers.DateTimeField(required=False, allow_null=True)
    duration_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )
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
    test_ends_at = serializers.DateTimeField()
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
            "test_ends_at",
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
