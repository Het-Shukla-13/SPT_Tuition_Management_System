import re

from django.db import transaction
from rest_framework import serializers

from apps.academics.models import (
    AcademicYear,
    Board,
    Chapter,
    School,
    Standard,
    Subject,
)

# "2026-27": the year it starts, a hyphen, the next year's last two digits.
YEAR_NAME = re.compile(r"(?P<first>\d{4})-(?P<second>\d{2})")


class _ReferenceSerializer(serializers.ModelSerializer):
    """
    Adds case-insensitive uniqueness checks. DRF can't derive validators from
    the database's Lower(...) constraints, so without this a duplicate would
    reach the database and fail as a 500 instead of a clean 400.

    ci_unique: tuples of field names that must be unique together, ignoring case.
    """

    ci_unique: tuple[tuple[str, ...], ...] = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        model = self.Meta.model
        for fields in self.ci_unique:
            values = {f: attrs.get(f, getattr(self.instance, f, None)) for f in fields}
            if any(v is None for v in values.values()):
                continue
            lookup = {f"{f}__iexact": v for f, v in values.items()}
            clash = model.objects.filter(**lookup)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                label = " + ".join(fields)
                raise serializers.ValidationError(
                    {
                        fields[0]: [
                            f"A {model._meta.verbose_name} with this {label} already exists."
                        ]
                    }
                )
        return attrs


class BoardSerializer(_ReferenceSerializer):
    ci_unique = (("code",),)

    class Meta:
        model = Board
        fields = ["id", "name", "code", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StandardSerializer(_ReferenceSerializer):
    class Meta:
        model = Standard
        fields = ["id", "name", "level", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubjectSerializer(_ReferenceSerializer):
    ci_unique = (("name",), ("code",))

    class Meta:
        model = Subject
        fields = ["id", "name", "code", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ChapterSerializer(_ReferenceSerializer):
    board_code = serializers.CharField(source="board.code", read_only=True)
    standard_name = serializers.CharField(source="standard.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Chapter
        fields = [
            "id",
            "board",
            "board_code",
            "standard",
            "standard_name",
            "subject",
            "subject_name",
            "number",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SchoolSerializer(_ReferenceSerializer):
    ci_unique = (("name", "city"),)
    board_code = serializers.CharField(
        source="board.code", read_only=True, default=None
    )

    class Meta:
        model = School
        fields = [
            "id",
            "name",
            "city",
            "board",
            "board_code",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AcademicYearSerializer(_ReferenceSerializer):
    # Declared explicitly so DRF doesn't attach unique validators for the
    # "one current year per board" constraint (save() handles the switch).
    is_current = serializers.BooleanField(required=False, default=False)
    board_code = serializers.CharField(source="board.code", read_only=True)

    class Meta:
        model = AcademicYear
        fields = [
            "id",
            "board",
            "board_code",
            "name",
            "start_date",
            "end_date",
            "is_current",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # DRF would auto-add a validator for the "single current year" DB
        # constraint and reject a new current year before save() can switch
        # the old one off. save() handles it; the database still enforces it.
        validators = []

    def validate_name(self, value):
        """One format everywhere, so boards' years line up by name (e.g. 2026-27)."""
        value = value.strip()
        match = YEAR_NAME.fullmatch(value)
        if not match:
            raise serializers.ValidationError("Use the format YYYY-YY, e.g. 2026-27.")
        first, second = int(match["first"]), int(match["second"])
        if second != (first + 1) % 100:
            raise serializers.ValidationError(
                f"The two years must follow on: {first}-{(first + 1) % 100:02d}."
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        match = YEAR_NAME.fullmatch(name or "")
        if start and match and int(match["first"]) != start.year:
            raise serializers.ValidationError(
                {
                    "name": [
                        f"A year starting in {start.year} should be called "
                        f"{start.year}-{(start.year + 1) % 100:02d}."
                    ]
                }
            )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": ["Must be after the start date."]}
            )
        if attrs.get("is_current") and attrs.get("is_active", True) is False:
            raise serializers.ValidationError(
                {"is_current": ["An inactive year can't be current."]}
            )
        board = attrs.get("board", getattr(self.instance, "board", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        clash = AcademicYear.objects.filter(board=board, name__iexact=name)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if board is not None and name and clash.exists():
            raise serializers.ValidationError(
                {"name": [f"{board} already has an academic year called {name}."]}
            )
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        # One current year per board: switching it on here switches that
        # board's old one off first (the database also enforces it).
        if self.validated_data.get("is_current"):
            board = self.validated_data.get("board") or self.instance.board
            others = AcademicYear.objects.select_for_update().filter(
                board=board, is_current=True
            )
            if self.instance is not None:
                others = others.exclude(pk=self.instance.pk)
            others.update(is_current=False)
        return super().save(**kwargs)
