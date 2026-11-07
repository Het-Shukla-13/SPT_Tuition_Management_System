from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.academics.models import Board, School, Standard, Subject
from apps.accounts.choices import OTPChannel
from apps.accounts.identifiers import normalize_identifier, normalize_phone
from apps.accounts.models import User
from apps.students.models import (
    StudentAcademicHistory,
    StudentAccess,
    StudentProfile,
    StudentSubject,
)


# ─────────────────────────────────────────────────────────────
# Small nested representations
# ─────────────────────────────────────────────────────────────
class _BoardRef(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ["id", "code", "name"]


class _StandardRef(serializers.ModelSerializer):
    class Meta:
        model = Standard
        fields = ["id", "name", "level"]


class _SchoolRef(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "city"]


class _SubjectRef(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "code"]


class StudentSubjectSerializer(serializers.ModelSerializer):
    subject = _SubjectRef()

    class Meta:
        model = StudentSubject
        fields = ["subject", "started_on", "ended_on"]


class LinkedLoginSerializer(serializers.ModelSerializer):
    """A login that can see the student (shown to admins)."""

    user_id = serializers.IntegerField(source="user.id")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    email = serializers.EmailField(source="user.email")
    phone = serializers.CharField(source="user.phone")
    invite_accepted = serializers.SerializerMethodField()

    class Meta:
        model = StudentAccess
        fields = [
            "user_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "invite_accepted",
            "granted_at",
        ]

    def get_invite_accepted(self, obj) -> bool:
        return obj.user.activated_at is not None


class AcademicHistorySerializer(serializers.ModelSerializer):
    academic_year = serializers.CharField(source="academic_year.name")
    board = serializers.CharField(source="board.code")
    standard = serializers.CharField(source="standard.name")
    school = serializers.CharField(source="school.__str__")

    class Meta:
        model = StudentAcademicHistory
        fields = [
            "id",
            "academic_year",
            "board",
            "standard",
            "school",
            "started_on",
            "ended_on",
            "reason",
        ]


# ─────────────────────────────────────────────────────────────
# Admin: read
# ─────────────────────────────────────────────────────────────
class StudentListSerializer(serializers.ModelSerializer):
    board = _BoardRef()
    standard = _StandardRef()
    school = _SchoolRef()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "admission_number",
            "first_name",
            "last_name",
            "board",
            "standard",
            "school",
            "status",
            "admission_date",
            "guardian_name",
            "guardian_phone",
            "created_at",
        ]


class StudentDetailSerializer(StudentListSerializer):
    subjects = serializers.SerializerMethodField()
    logins = serializers.SerializerMethodField()

    class Meta(StudentListSerializer.Meta):
        fields = [
            *StudentListSerializer.Meta.fields,
            "date_of_birth",
            "gender",
            "address",
            "guardian_relation",
            "guardian_email",
            "left_on",
            "remarks",
            "subjects",
            "logins",
            "updated_at",
        ]

    def get_subjects(self, obj) -> list[dict]:
        current = obj.subjects.filter(ended_on__isnull=True).select_related("subject")
        return StudentSubjectSerializer(current, many=True).data

    def get_logins(self, obj) -> list[dict]:
        links = obj.access_links.filter(revoked_at__isnull=True).select_related("user")
        return LinkedLoginSerializer(links, many=True).data


# ─────────────────────────────────────────────────────────────
# Admin: write
# ─────────────────────────────────────────────────────────────
def _normalize_guardian(attrs: dict) -> dict:
    phone = attrs.get("guardian_phone")
    if phone:
        try:
            attrs["guardian_phone"] = normalize_phone(phone)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"guardian_phone": exc.messages}
            ) from None
    return attrs


class NewLoginSerializer(serializers.Serializer):
    """A parent/student login to create and link (role PORTAL)."""

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.CharField(max_length=254, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate(self, attrs):
        errors = {}
        for channel, field in (
            (OTPChannel.EMAIL, "email"),
            (OTPChannel.PHONE, "phone"),
        ):
            raw = attrs.get(field) or None
            attrs[field] = None
            if raw:
                try:
                    attrs[field] = normalize_identifier(channel, raw)
                except DjangoValidationError as exc:
                    errors[field] = exc.messages
        if not errors and not attrs["email"] and not attrs["phone"]:
            errors["non_field_errors"] = ["Give an email, a phone number, or both."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class _PersonalFields(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=StudentProfile.Gender.choices, required=False, allow_blank=True
    )
    address = serializers.CharField(required=False, allow_blank=True)
    guardian_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    guardian_relation = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    guardian_phone = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        return _normalize_guardian(super().validate(attrs))


class AdmissionSerializer(_PersonalFields):
    """The admin's "Add new student" form."""

    board = serializers.PrimaryKeyRelatedField(queryset=Board.objects.all())
    standard = serializers.PrimaryKeyRelatedField(queryset=Standard.objects.all())
    school = serializers.PrimaryKeyRelatedField(queryset=School.objects.all())
    admission_date = serializers.DateField(required=False)
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), many=True, allow_empty=False
    )
    link_user_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False,
        default=list,
        help_text="Existing parent/student logins that should see this student (e.g. a sibling's parent).",
    )
    new_logins = NewLoginSerializer(
        many=True,
        required=False,
        default=list,
        help_text="New parent/student logins to create, link and invite (SMS/email).",
    )
    confirm_duplicate = serializers.BooleanField(
        default=False,
        help_text="Admit even if a similar student exists (after checking the warning).",
    )

    PROFILE_FIELDS = (
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
        "board",
        "standard",
        "school",
        "admission_date",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        ids = [s.pk for s in attrs["subjects"]]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                {"subjects": ["A subject is listed twice."]}
            )
        return attrs

    def split(self) -> dict:
        data = self.validated_data
        return {
            "profile": {k: data[k] for k in self.PROFILE_FIELDS if k in data},
            "subjects": data["subjects"],
            "link_users": data["link_user_ids"],
            "new_logins": data["new_logins"],
            "confirm_duplicate": data["confirm_duplicate"],
        }


class StudentUpdateSerializer(_PersonalFields):
    """PATCH: personal details only (academic changes have their own endpoint)."""

    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)


class AcademicChangeSerializer(serializers.Serializer):
    board = serializers.PrimaryKeyRelatedField(
        queryset=Board.objects.all(), required=False
    )
    standard = serializers.PrimaryKeyRelatedField(
        queryset=Standard.objects.all(), required=False
    )
    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(), required=False
    )
    reason = serializers.ChoiceField(
        choices=[
            c
            for c in StudentAcademicHistory.Reason.choices
            if c[0] != StudentAcademicHistory.Reason.ADMISSION
        ]
    )

    def validate(self, attrs):
        if not any(attrs.get(f) for f in ("board", "standard", "school")):
            raise serializers.ValidationError(
                "Give a new board, standard and/or school."
            )
        return attrs


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=StudentProfile.Status.choices)


class SubjectsSerializer(serializers.Serializer):
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), many=True, allow_empty=False
    )


class AccessCreateSerializer(serializers.Serializer):
    """Give a login access: an existing one (user_id) OR a new one (new_login)."""

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False
    )
    new_login = NewLoginSerializer(required=False)

    def validate(self, attrs):
        if bool(attrs.get("user_id")) == bool(attrs.get("new_login")):
            raise serializers.ValidationError(
                "Give exactly one of user_id or new_login."
            )
        return attrs


class AdmissionResultSerializer(serializers.Serializer):
    """Documentation only."""

    student = StudentDetailSerializer()
    invite_sent = serializers.DictField(
        help_text="Per new login id: {email: bool, phone: bool}."
    )


# ─────────────────────────────────────────────────────────────
# Portal (parents / students)
# ─────────────────────────────────────────────────────────────
class PortalStudentSerializer(serializers.ModelSerializer):
    board = _BoardRef()
    standard = _StandardRef()
    school = _SchoolRef()
    subjects = serializers.SerializerMethodField()
    is_selected = serializers.SerializerMethodField(
        help_text="The student this device picked last."
    )

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "admission_number",
            "first_name",
            "last_name",
            "board",
            "standard",
            "school",
            "status",
            "admission_date",
            "subjects",
            "is_selected",
        ]

    def get_subjects(self, obj) -> list[dict]:
        current = obj.subjects.filter(ended_on__isnull=True).select_related("subject")
        return [_SubjectRef(ss.subject).data for ss in current]

    def get_is_selected(self, obj) -> bool:
        return obj.pk == self.context.get("selected_student_id")
