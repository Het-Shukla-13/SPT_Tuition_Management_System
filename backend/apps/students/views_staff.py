"""
Staff student lookup: GET /api/v1/staff/students/ (admins and teachers).

Teachers need to pick students when assigning tests and notes, but the full
student records (guardian phone, address, fees...) are for admins only. This
answers with the minimum needed to recognise a student, filtered the way a
teacher thinks: "Std 10, CBSE, taking Maths".
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.views import APIView

from apps.common.permissions import IsStaff
from apps.common.responses import ApiResponse
from apps.students.models import StudentProfile

# One assignment call takes at most 500 students; a lookup never needs more.
MAX_RESULTS = 500


class StaffStudentSerializer(serializers.ModelSerializer):
    board_code = serializers.CharField(source="board.code")
    standard_name = serializers.CharField(source="standard.name")
    school_name = serializers.CharField(source="school.name")

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "admission_number",
            "first_name",
            "last_name",
            "board",
            "board_code",
            "standard",
            "standard_name",
            "school",
            "school_name",
        ]


class StaffStudentLookupView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["Staff: students"],
        summary="Find active students to assign tests/notes to",
        description=(
            "Active students only, minimal details (no guardian contact or fees). "
            f"Not paginated: at most {MAX_RESULTS} results, ordered by name."
        ),
        parameters=[
            OpenApiParameter("board", int),
            OpenApiParameter("standard", int),
            OpenApiParameter("school", int),
            OpenApiParameter(
                "subject", int, description="Currently taking this subject."
            ),
            OpenApiParameter("search", str, description="Name or admission number."),
        ],
        responses={200: StaffStudentSerializer(many=True)},
    )
    def get(self, request):
        queryset = StudentProfile.objects.filter(
            status=StudentProfile.Status.ACTIVE
        ).select_related("board", "standard", "school")
        params = request.query_params
        for field in ("board", "standard", "school"):
            value = params.get(field)
            if value and value.isdigit():
                queryset = queryset.filter(**{f"{field}_id": int(value)})
        subject = params.get("subject")
        if subject and subject.isdigit():
            queryset = queryset.filter(
                subjects__subject_id=int(subject), subjects__ended_on__isnull=True
            )
        term = (params.get("search") or "").strip()
        if term:
            queryset = queryset.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(admission_number__icontains=term)
            )
        students = queryset.distinct().order_by("first_name", "last_name")[:MAX_RESULTS]
        return ApiResponse.success(
            data=StaffStudentSerializer(students, many=True).data
        )
