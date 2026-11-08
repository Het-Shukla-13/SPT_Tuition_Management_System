"""
Admin:  /api/v1/admin/fee-structures/  /api/v1/admin/fees/...  /api/v1/admin/rollover/...
Portal: /api/v1/portal/students/{student_id}/fees/...
Teachers have no access to fees.
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin, IsPortalUser
from apps.common.request_utils import client_ip
from apps.common.responses import ApiResponse
from apps.common.viewsets import EnvelopeModelViewSet
from apps.fees import rollover, services
from apps.fees.models import FeeStructure, LedgerEntry, StudentFeeAccount
from apps.fees.serializers import (
    AdjustmentSerializer,
    AgreedFeeSerializer,
    FeeAccountDetailSerializer,
    FeeAccountListSerializer,
    FeeStructureSerializer,
    LedgerEntrySerializer,
    PaymentListSerializer,
    PaymentSerializer,
    PortalFeeAccountSerializer,
    RefundSerializer,
    ReverseSerializer,
    RolloverApplySerializer,
    RolloverPreviewSerializer,
)
from apps.students.services import get_linked_student

FEES_TAG = ["Admin: fees"]


def _account(pk) -> StudentFeeAccount:
    return get_object_or_404(StudentFeeAccount, pk=pk)


def _detail(account_id) -> dict:
    return FeeAccountDetailSerializer(services.account_with_totals(account_id)).data


# ─── Fee structures ──────────────────────────────────────────
@extend_schema_view(
    list=extend_schema(tags=FEES_TAG, summary="Fee structures"),
    retrieve=extend_schema(tags=FEES_TAG, summary="Get a fee structure"),
    create=extend_schema(tags=FEES_TAG, summary="Create a fee structure"),
    partial_update=extend_schema(
        tags=FEES_TAG, summary="Update (never changes existing students' agreed fees)"
    ),
)
class FeeStructureViewSet(EnvelopeModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = FeeStructureSerializer
    queryset = FeeStructure.objects.select_related("academic_year__board", "standard")
    filterset_fields = [
        "academic_year",
        "academic_year__board",
        "standard",
        "is_active",
    ]
    ordering_fields = ["standard__level", "total_fee"]


# ─── Accounts ────────────────────────────────────────────────
class _Num(OpenApiParameter):
    def __init__(self, name, description=""):
        super().__init__(name, OpenApiTypes.NUMBER, description=description)


@extend_schema(tags=FEES_TAG)
class FeeAccountListView(generics.ListAPIView):
    """Fees table: one row per student per academic year."""

    permission_classes = [IsAdmin]
    serializer_class = FeeAccountListSerializer
    filterset_fields = {
        "academic_year": ["exact"],
        "academic_year__board": ["exact"],
        "student__standard": ["exact"],
        "student__school": ["exact"],
        "student__status": ["exact"],
        "student__admission_date": ["gte", "lte"],
    }
    search_fields = [
        "student__first_name",
        "student__last_name",
        "student__admission_number",
        "student__guardian_phone",
    ]
    ordering_fields = [
        "pending",
        "total",
        "paid",
        "credit",
        "last_payment_date",
        "student__first_name",
        "student__standard__level",
    ]
    ordering = ["-pending"]

    RANGES = {"pending": "pending", "paid": "paid", "total": "total"}
    STATUSES = {
        "PAID",
        "PARTIAL",
        "PENDING",
        "CREDIT",
        "CARRIED_FORWARD",
        "OVERDUE",
        "ENDING_SOON",
    }

    def get_queryset(self):
        qs = services.with_totals(
            StudentFeeAccount.objects.select_related(
                "student__standard", "student__board", "academic_year"
            )
        )
        params = self.request.query_params
        for prefix, field in self.RANGES.items():
            for bound, lookup in (("min", "gte"), ("max", "lte")):
                value = params.get(f"{prefix}_{bound}")
                if value not in (None, ""):
                    qs = qs.filter(**{f"{field}__{lookup}": value})
        status = (params.get("status") or "").upper()
        if status == "OVERDUE":
            qs = qs.filter(is_overdue=True)
        elif status == "ENDING_SOON":
            qs = qs.filter(is_ending_soon=True)
        elif status in self.STATUSES:
            qs = qs.filter(status=status)
        return qs

    @extend_schema(
        summary="Fees table (filter / search / sort)",
        parameters=[
            OpenApiParameter(
                "status",
                OpenApiTypes.STR,
                enum=[
                    "PAID",
                    "PARTIAL",
                    "PENDING",
                    "CREDIT",
                    "CARRIED_FORWARD",
                    "OVERDUE",
                    "ENDING_SOON",
                ],
            ),
            _Num("pending_min"),
            _Num("pending_max"),
            _Num("paid_min"),
            _Num("paid_max"),
            _Num("total_min"),
            _Num("total_max"),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class FeeAccountDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Fee account with full ledger",
        responses={200: FeeAccountDetailSerializer},
    )
    def get(self, request, pk: int):
        return ApiResponse.success(data=_detail(_account(pk).pk))


class StudentFeeAccountsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="All fee accounts of one student (every year)",
        responses={200: FeeAccountDetailSerializer(many=True)},
    )
    def get(self, request, student_id: int):
        accounts = services.with_totals(
            StudentFeeAccount.objects.filter(student_id=student_id).select_related(
                "student__standard", "student__board", "academic_year"
            )
        ).order_by("-academic_year__start_date")
        return ApiResponse.success(
            data=FeeAccountDetailSerializer(accounts, many=True).data
        )


class PaymentCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Record a payment",
        description=(
            "Send an `Idempotency-Key` header (any unique string per Save click, e.g. a UUID). "
            "Retrying with the same key returns the original payment instead of recording it twice."
        ),
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", OpenApiTypes.STR, OpenApiParameter.HEADER
            )
        ],
        request=PaymentSerializer,
        responses={
            201: FeeAccountDetailSerializer,
            200: OpenApiResponse(description="Duplicate submit: original returned"),
        },
    )
    def post(self, request, pk: int):
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = (request.headers.get("Idempotency-Key") or "").strip()[:64] or None
        entry, created = services.record_payment(
            actor=request.user,
            account=_account(pk),
            idempotency_key=key,
            ip=client_ip(request),
            **serializer.validated_data,
        )
        data = {"payment": LedgerEntrySerializer(entry).data, "account": _detail(pk)}
        if created:
            return ApiResponse.created(
                message=f"Payment recorded ({entry.receipt_number}).", data=data
            )
        return ApiResponse.success(
            message="Already recorded (duplicate submit ignored).", data=data
        )


class AdjustmentCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Add an adjustment (+ extra charge / - concession)",
        request=AdjustmentSerializer,
        responses={201: FeeAccountDetailSerializer},
    )
    def post(self, request, pk: int):
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.add_adjustment(
            actor=request.user,
            account=_account(pk),
            ip=client_ip(request),
            **serializer.validated_data,
        )
        return ApiResponse.created(message="Adjustment added.", data=_detail(pk))


class AgreedFeeView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Change the agreed fee (recorded as an adjustment)",
        request=AgreedFeeSerializer,
        responses={200: FeeAccountDetailSerializer},
    )
    def post(self, request, pk: int):
        serializer = AgreedFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_agreed_fee(
            actor=request.user,
            account=_account(pk),
            new_fee=serializer.validated_data["agreed_fee"],
            reason=serializer.validated_data["reason"],
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Agreed fee updated.", data=_detail(pk))


class RefundCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Record a refund",
        request=RefundSerializer,
        responses={201: FeeAccountDetailSerializer},
    )
    def post(self, request, pk: int):
        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.record_refund(
            actor=request.user,
            account=_account(pk),
            ip=client_ip(request),
            **serializer.validated_data,
        )
        return ApiResponse.created(message="Refund recorded.", data=_detail(pk))


class ReversePaymentView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Reverse a wrong payment (kept in history)",
        request=ReverseSerializer,
        responses={201: FeeAccountDetailSerializer},
    )
    def post(self, request, entry_id: int):
        serializer = ReverseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = get_object_or_404(LedgerEntry, pk=entry_id)
        services.reverse_payment(
            actor=request.user,
            entry=entry,
            reason=serializer.validated_data["reason"],
            ip=client_ip(request),
        )
        return ApiResponse.created(
            message="Payment reversed.", data=_detail(entry.account_id)
        )


@extend_schema(tags=FEES_TAG)
class PaymentListView(generics.ListAPIView):
    """All payments across students."""

    permission_classes = [IsAdmin]
    serializer_class = PaymentListSerializer
    filterset_fields = {
        "entry_date": ["gte", "lte"],
        "method": ["exact"],
        "amount": ["gte", "lte"],
        "recorded_by": ["exact"],
        "account__academic_year": ["exact"],
    }
    search_fields = [
        "account__student__first_name",
        "account__student__last_name",
        "account__student__admission_number",
        "receipt_number",
        "reference",
    ]
    ordering_fields = ["entry_date", "amount", "created_at"]
    ordering = ["-entry_date", "-id"]

    def get_queryset(self):
        qs = LedgerEntry.objects.filter(
            entry_type=LedgerEntry.Type.PAYMENT
        ).select_related(
            "account__student", "account__academic_year", "recorded_by", "reversed_by"
        )
        reversed_param = self.request.query_params.get("reversed")
        if reversed_param == "true":
            qs = qs.filter(reversed_by__isnull=False)
        elif reversed_param == "false":
            qs = qs.filter(reversed_by__isnull=True)
        return qs

    @extend_schema(
        summary="All payments (filter / search / sort)",
        parameters=[OpenApiParameter("reversed", OpenApiTypes.BOOL)],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def _receipt_response(entry: LedgerEntry) -> HttpResponse:
    response = HttpResponse(services.receipt_pdf(entry), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{entry.receipt_number}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


class ReceiptView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=FEES_TAG,
        summary="Payment receipt (PDF)",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request, entry_id: int):
        entry = get_object_or_404(
            LedgerEntry, pk=entry_id, entry_type=LedgerEntry.Type.PAYMENT
        )
        return _receipt_response(entry)


# ─── Rollover ────────────────────────────────────────────────
ROLLOVER_TAG = ["Admin: year-end rollover"]


class RolloverPreviewView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ROLLOVER_TAG,
        summary="Preview the year-end rollover for a board",
        request=RolloverPreviewSerializer,
        responses={
            200: OpenApiResponse(
                description="One row per active student: suggested_action, to_standard, suggested_agreed_fee, balance_to_carry, already_rolled_over"
            )
        },
    )
    def post(self, request):
        serializer = RolloverPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = rollover.preview(**serializer.validated_data)
        return ApiResponse.success(data=rows)


class RolloverApplyView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ROLLOVER_TAG,
        summary="Apply the rollover (per-student results)",
        request=RolloverApplySerializer,
        responses={
            200: OpenApiResponse(
                description='{"done": [...], "failed": [{"student_id", "reason"}]}'
            )
        },
    )
    def post(self, request):
        serializer = RolloverApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = rollover.apply(
            actor=request.user, ip=client_ip(request), **serializer.validated_data
        )
        return ApiResponse.success(
            message=f"Rolled over {len(result['done'])}, failed {len(result['failed'])}.",
            data=result,
        )


# ─── Portal ──────────────────────────────────────────────────
PORTAL_TAG = ["Portal: fees"]


class PortalFeesView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="My student's fees, every year (read-only)",
        responses={200: PortalFeeAccountSerializer(many=True)},
    )
    def get(self, request, student_id: int):
        student = get_linked_student(request.user, student_id)
        accounts = services.with_totals(
            StudentFeeAccount.objects.filter(student=student).select_related(
                "student__standard", "student__board", "academic_year"
            )
        ).order_by("-academic_year__start_date")
        return ApiResponse.success(
            data=PortalFeeAccountSerializer(accounts, many=True).data
        )


class PortalReceiptView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="Payment receipt (PDF)",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request, student_id: int, entry_id: int):
        student = get_linked_student(request.user, student_id)
        entry = get_object_or_404(
            LedgerEntry,
            pk=entry_id,
            entry_type=LedgerEntry.Type.PAYMENT,
            account__student=student,
        )
        return _receipt_response(entry)
