from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.academics.models import Board, Standard
from apps.accounts.identifiers import normalize_phone
from apps.enquiries.models import AdmissionEnquiry
from apps.students.models import StudentProfile


class PublicEnquirySerializer(serializers.Serializer):
    """The homepage form. `website` is a honeypot: humans never see or fill it."""

    parent_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField(required=False, allow_blank=True)
    student_name = serializers.CharField(max_length=150)
    standard = serializers.PrimaryKeyRelatedField(
        queryset=Standard.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    board = serializers.PrimaryKeyRelatedField(
        queryset=Board.objects.filter(is_active=True), required=False, allow_null=True
    )
    medium = serializers.ChoiceField(
        choices=StudentProfile.Medium.choices, required=False, allow_blank=True
    )
    school_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None


class AdminEnquirySerializer(serializers.ModelSerializer):
    standard_name = serializers.CharField(
        source="standard.name", read_only=True, default=None
    )
    board_code = serializers.CharField(
        source="board.code", read_only=True, default=None
    )

    class Meta:
        model = AdmissionEnquiry
        fields = [
            "id",
            "parent_name",
            "phone",
            "email",
            "student_name",
            "standard",
            "standard_name",
            "board",
            "board_code",
            "medium",
            "school_name",
            "message",
            "source",
            "status",
            "notes",
            "handled_by",
            "created_by",
            "student",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class StaffEnquirySerializer(PublicEnquirySerializer):
    """An enquiry recorded by staff: a parent walked in or phoned."""

    website = None  # the honeypot is only for the public form
    source = serializers.ChoiceField(
        choices=[c for c in AdmissionEnquiry.Source.choices if c[0] != "WEBSITE"],
        default=AdmissionEnquiry.Source.WALK_IN,
    )
    status = serializers.ChoiceField(
        choices=[
            (AdmissionEnquiry.Status.NEW, "New"),
            (AdmissionEnquiry.Status.CONTACTED, "Contacted"),
        ],
        default=AdmissionEnquiry.Status.CONTACTED,
        help_text="They usually already spoke to staff, so CONTACTED by default.",
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class EnquiryUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=AdmissionEnquiry.Status.choices, required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    student = serializers.PrimaryKeyRelatedField(
        queryset=StudentProfile.objects.all(),
        required=False,
        allow_null=True,
        help_text="The student admitted from this enquiry.",
    )

    def validate(self, attrs):
        if attrs.get("student") and attrs.get("status", "ACCEPTED") != "ACCEPTED":
            raise serializers.ValidationError(
                {"student": ["Only an ACCEPTED enquiry can be linked to a student."]}
            )
        if attrs.get("student"):
            attrs["status"] = AdmissionEnquiry.Status.ACCEPTED
        return attrs
