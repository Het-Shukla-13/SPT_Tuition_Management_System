from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.academics.models import AcademicYear, Board
from apps.fees.models import FeeStructure, LedgerEntry, StudentFeeAccount
from apps.fees.rollover import ACTIONS

MONEY = {"max_digits": 12, "decimal_places": 2}


class FeeStructureSerializer(serializers.ModelSerializer):
    board_code = serializers.CharField(
        source="academic_year.board.code", read_only=True
    )
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    standard_name = serializers.CharField(source="standard.name", read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "academic_year",
            "academic_year_name",
            "board_code",
            "standard",
            "standard_name",
            "total_fee",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"total_fee": {"min_value": 0}}


class LedgerEntrySerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(
        source="recorded_by.full_name", read_only=True, default=None
    )
    reversed = serializers.SerializerMethodField()

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "entry_type",
            "amount",
            "entry_date",
            "method",
            "reference",
            "remarks",
            "visible_to_student",
            "receipt_number",
            "reverses",
            "reversed",
            "recorded_by",
            "recorded_by_name",
            "created_at",
        ]

    def get_reversed(self, obj) -> bool:
        return obj.entry_type == LedgerEntry.Type.PAYMENT and hasattr(
            obj, "reversed_by"
        )


class _AccountTotals(serializers.Serializer):
    total = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    pending = serializers.DecimalField(**MONEY)
    credit = serializers.DecimalField(**MONEY)
    status = serializers.CharField()
    is_overdue = serializers.BooleanField()
    is_ending_soon = serializers.BooleanField()
    last_payment_date = serializers.DateField(allow_null=True)


class FeeAccountListSerializer(serializers.ModelSerializer, _AccountTotals):
    student_name = serializers.CharField(source="student.full_name")
    admission_number = serializers.CharField(source="student.admission_number")
    standard = serializers.CharField(source="student.standard.name")
    board = serializers.CharField(source="student.board.code")
    academic_year_name = serializers.CharField(source="academic_year.name")
    due_date = serializers.DateField(source="academic_year.end_date")

    class Meta:
        model = StudentFeeAccount
        fields = [
            "id",
            "student",
            "student_name",
            "admission_number",
            "standard",
            "board",
            "academic_year",
            "academic_year_name",
            "due_date",
            "agreed_fee",
            "opening_balance",
            "total",
            "paid",
            "pending",
            "credit",
            "status",
            "is_overdue",
            "is_ending_soon",
            "last_payment_date",
        ]


class FeeAccountDetailSerializer(FeeAccountListSerializer):
    entries = serializers.SerializerMethodField()

    class Meta(FeeAccountListSerializer.Meta):
        fields = [
            *FeeAccountListSerializer.Meta.fields,
            "opening_balance_reason",
            "entries",
        ]

    @extend_schema_field(LedgerEntrySerializer(many=True))
    def get_entries(self, obj) -> list[dict]:
        return LedgerEntrySerializer(
            obj.entries.select_related("recorded_by"), many=True
        ).data


class PaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY)
    entry_date = serializers.DateField(default=timezone.localdate)
    method = serializers.ChoiceField(choices=LedgerEntry.Method.choices)
    reference = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
    visible_to_student = serializers.BooleanField(default=True)


class AdjustmentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        **MONEY, help_text="+ adds to what's owed, - reduces it (e.g. a concession)."
    )
    reason = serializers.CharField()
    visible_to_student = serializers.BooleanField(default=True)


class AgreedFeeSerializer(serializers.Serializer):
    agreed_fee = serializers.DecimalField(**MONEY, min_value=0)
    reason = serializers.CharField()


class RefundSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY)
    entry_date = serializers.DateField(default=timezone.localdate)
    method = serializers.ChoiceField(choices=LedgerEntry.Method.choices)
    reference = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    reason = serializers.CharField()


class ReverseSerializer(serializers.Serializer):
    reason = serializers.CharField()


class PaymentListSerializer(LedgerEntrySerializer):
    student_name = serializers.CharField(source="account.student.full_name")
    admission_number = serializers.CharField(source="account.student.admission_number")
    academic_year_name = serializers.CharField(source="account.academic_year.name")

    class Meta(LedgerEntrySerializer.Meta):
        fields = [
            *LedgerEntrySerializer.Meta.fields,
            "account",
            "student_name",
            "admission_number",
            "academic_year_name",
        ]


class RolloverPreviewSerializer(serializers.Serializer):
    board = serializers.PrimaryKeyRelatedField(queryset=Board.objects.all())
    to_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects.all())


class RolloverItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(min_value=1)
    action = serializers.ChoiceField(choices=ACTIONS)
    agreed_fee = serializers.DecimalField(
        **MONEY, min_value=0, required=False, allow_null=True
    )


class RolloverApplySerializer(RolloverPreviewSerializer):
    items = RolloverItemSerializer(many=True, allow_empty=False)
    make_current = serializers.BooleanField(
        default=True, help_text="Also make to_year the board's current year."
    )


# ─── Portal ──────────────────────────────────────────────────
class PortalLedgerEntrySerializer(serializers.ModelSerializer):
    """Remarks only when marked visible to students."""

    remarks = serializers.SerializerMethodField()

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "entry_type",
            "amount",
            "entry_date",
            "method",
            "reference",
            "receipt_number",
            "remarks",
        ]

    def get_remarks(self, obj) -> str:
        return obj.remarks if obj.visible_to_student else ""


class PortalFeeAccountSerializer(FeeAccountListSerializer):
    entries = serializers.SerializerMethodField()

    class Meta(FeeAccountListSerializer.Meta):
        fields = [
            "id",
            "academic_year_name",
            "due_date",
            "agreed_fee",
            "opening_balance",
            "total",
            "paid",
            "pending",
            "credit",
            "status",
            "is_overdue",
            "is_ending_soon",
            "last_payment_date",
            "entries",
        ]

    @extend_schema_field(PortalLedgerEntrySerializer(many=True))
    def get_entries(self, obj) -> list[dict]:
        return PortalLedgerEntrySerializer(obj.entries.all(), many=True).data
