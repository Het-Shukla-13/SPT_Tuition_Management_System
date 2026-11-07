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
    # Declared explicitly so DRF doesn't attach a field-level unique validator
    # for the "single current year" constraint (save() handles the switch).
    is_current = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = AcademicYear
        fields = [
            "id",
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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": ["Must be after the start date."]}
            )
        if attrs.get("is_current") and attrs.get("is_active", True) is False:
            raise serializers.ValidationError(
                {"is_current": ["An inactive year can't be current."]}
            )
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        # Only one current year: switching it on here switches the old one off
        # first (the database also enforces "at most one current").
        if self.validated_data.get("is_current"):
            others = AcademicYear.objects.select_for_update().filter(is_current=True)
            if self.instance is not None:
                others = others.exclude(pk=self.instance.pk)
            others.update(is_current=False)
        return super().save(**kwargs)
