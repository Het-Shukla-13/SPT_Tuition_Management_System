"""
GET /api/v1/staff/dashboard/                       admins (with fees) and teachers (without)
GET /api/v1/portal/students/{student_id}/overview/  parent / student
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.views import APIView

from apps.academics.models import Board
from apps.common.exceptions import ValidationFailed
from apps.common.permissions import IsPortalUser, IsStaff, has_role
from apps.common.responses import ApiResponse
from apps.dashboard.services import staff_dashboard, student_overview
from apps.students.services import get_linked_student


class StaffDashboardView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["Dashboards"],
        summary="Admin / teacher dashboard",
        description=(
            "Student counts, new admissions, active students per standard, recent admissions, "
            "tests/notes activity (upcoming tests, tests waiting for marks). Admins also get the "
            "fees summary for each board's current year; teachers never see fees."
        ),
        parameters=[
            OpenApiParameter(
                "board", OpenApiTypes.INT, description="Limit to one board."
            ),
            OpenApiParameter(
                "days",
                OpenApiTypes.INT,
                description="'New admissions' window (default 30, max 366).",
            ),
        ],
        responses={
            200: OpenApiResponse(description="students / learning / fees (admins only)")
        },
    )
    def get(self, request):
        board = None
        if request.query_params.get("board"):
            board = get_object_or_404(Board, pk=request.query_params["board"])
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            raise ValidationFailed(details={"days": ["Must be a number."]}) from None
        if not 1 <= days <= 366:
            raise ValidationFailed(details={"days": ["Between 1 and 366."]})
        data = staff_dashboard(
            include_fees=has_role(request.user, "ADMIN"), board=board, days=days
        )
        return ApiResponse.success(data=data)


class PortalOverviewView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=["Dashboards"],
        summary="Student overview (parent / student home screen)",
        description="Student details, upcoming tests, recent results and notes, current fee status.",
        responses={
            200: OpenApiResponse(
                description="student / upcoming_tests / recent_results / recent_notes / fees"
            )
        },
    )
    def get(self, request, student_id: int):
        student = get_linked_student(request.user, student_id)
        return ApiResponse.success(data=student_overview(student))
