"""
Student endpoints.

Admin:  /api/v1/admin/students/...   (IsAdmin)
Portal: /api/v1/portal/students/...  (IsPortalUser; only linked students)
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.services.sessions import SID_CLAIM
from apps.common.permissions import IsAdmin, IsPortalUser
from apps.common.request_utils import client_ip
from apps.common.responses import ApiResponse
from apps.students.models import StudentProfile
from apps.students.serializers import (
    AcademicChangeSerializer,
    AcademicHistorySerializer,
    AccessCreateSerializer,
    AdmissionResultSerializer,
    AdmissionSerializer,
    LinkedLoginSerializer,
    PortalStudentSerializer,
    StatusSerializer,
    StudentDetailSerializer,
    StudentListSerializer,
    StudentUpdateSerializer,
    SubjectsSerializer,
)
from apps.students.services import (
    admit_student,
    change_academic,
    get_linked_student,
    grant_access,
    linked_students,
    photo_response,
    remove_photo,
    revoke_access,
    select_student,
    selected_student_id,
    set_photo,
    set_status,
    set_subjects,
    update_student,
)

ADMIN_TAG = ["Admin: students"]
PORTAL_TAG = ["Portal: students"]


def _student(pk: int) -> StudentProfile:
    return get_object_or_404(
        StudentProfile.objects.select_related("board", "standard", "school"), pk=pk
    )


def _detail(student: StudentProfile) -> dict:
    return StudentDetailSerializer(_student(student.pk)).data


# ─────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────
@extend_schema(tags=ADMIN_TAG)
class AdminStudentListView(generics.ListAPIView):
    """
    ?search=   name, admission no., guardian name/phone/email, linked login's phone/email
    ?standard= ?board= ?school= ?status=
    ?ordering= first_name | last_name | admission_date | standard__level | created_at
    """

    permission_classes = [IsAdmin]
    serializer_class = StudentListSerializer
    filterset_fields = ["standard", "board", "school", "status", "medium"]
    ordering_fields = [
        "first_name",
        "last_name",
        "admission_date",
        "standard__level",
        "created_at",
    ]
    ordering = ["first_name", "last_name"]

    def get_queryset(self):
        queryset = StudentProfile.objects.select_related("board", "standard", "school")
        term = (self.request.query_params.get("search") or "").strip()
        if term:
            # Explicit search (instead of SearchFilter) so the login join only
            # matches ACTIVE links and duplicates are removed.
            active_login = Q(access_links__revoked_at__isnull=True) & (
                Q(access_links__user__email__icontains=term)
                | Q(access_links__user__phone__icontains=term)
            )
            queryset = queryset.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(admission_number__icontains=term)
                | Q(guardian_name__icontains=term)
                | Q(guardian_phone__icontains=term)
                | Q(guardian_email__icontains=term)
                | active_login
            ).distinct()
        return queryset

    @extend_schema(summary="List / search students")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Admit a new student (the admission form)",
        description=(
            "Creates the student profile, their subjects and the first academic-history "
            "row, and links the logins that can see them: existing ones (`link_user_ids`, "
            "e.g. a sibling's parent) and/or new ones (`new_logins`, invited by SMS/email). "
            "If a similar student exists you get `409 POSSIBLE_DUPLICATE_STUDENT` with the "
            "candidates; resend with `confirm_duplicate: true` to admit anyway."
        ),
        request=AdmissionSerializer,
        responses={
            201: AdmissionResultSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR / NO_CURRENT_ACADEMIC_YEAR / INACTIVE_REFERENCE / NOT_A_PORTAL_LOGIN"
            ),
            409: OpenApiResponse(
                description="POSSIBLE_DUPLICATE_STUDENT / CONTACT_IN_USE"
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = AdmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student, invites = admit_student(
            actor=request.user, **serializer.split(), ip=client_ip(request)
        )
        return ApiResponse.created(
            message=f"Student admitted ({student.admission_number}).",
            data={"student": _detail(student), "invite_sent": invites},
        )


class AdminStudentDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Get a student",
        responses={200: StudentDetailSerializer},
    )
    def get(self, request, pk: int):
        return ApiResponse.success(data=_detail(_student(pk)))

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Edit personal details",
        description="Board/standard/school use `/academic/`; status uses `/status/`.",
        request=StudentUpdateSerializer,
        responses={200: StudentDetailSerializer},
    )
    def patch(self, request, pk: int):
        serializer = StudentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        student = update_student(
            actor=request.user,
            student=_student(pk),
            changes=serializer.validated_data,
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Updated.", data=_detail(student))


class AdminStudentAcademicView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Change board / standard / school (keeps history)",
        request=AcademicChangeSerializer,
        responses={
            200: StudentDetailSerializer,
            400: OpenApiResponse(
                description="NOTHING_CHANGED / INACTIVE_REFERENCE / NO_CURRENT_ACADEMIC_YEAR"
            ),
        },
    )
    def post(self, request, pk: int):
        serializer = AcademicChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        student = change_academic(
            actor=request.user,
            student=_student(pk),
            board=data.get("board"),
            standard=data.get("standard"),
            school=data.get("school"),
            reason=data["reason"],
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Academic details changed.", data=_detail(student)
        )


class AdminStudentHistoryView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Academic history",
        responses={200: AcademicHistorySerializer(many=True)},
    )
    def get(self, request, pk: int):
        history = _student(pk).academic_history.select_related(
            "academic_year", "board", "standard", "school"
        )
        return ApiResponse.success(
            data=AcademicHistorySerializer(history, many=True).data
        )


class AdminStudentStatusView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Set status (ACTIVE / ON_HOLD / LEFT)",
        description="Leaving keeps everything (fees, tests, history). Idempotent.",
        request=StatusSerializer,
        responses={200: StudentDetailSerializer},
    )
    def post(self, request, pk: int):
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = set_status(
            actor=request.user,
            student=_student(pk),
            status=serializer.validated_data["status"],
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Status updated.", data=_detail(student))


class AdminStudentSubjectsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Replace the student's subjects (dropped ones kept as history)",
        request=SubjectsSerializer,
        responses={200: StudentDetailSerializer},
    )
    def put(self, request, pk: int):
        serializer = SubjectsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = set_subjects(
            actor=request.user,
            student=_student(pk),
            subjects=serializer.validated_data["subjects"],
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Subjects updated.", data=_detail(student))


class AdminStudentAccessView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Logins that can see this student",
        responses={200: LinkedLoginSerializer(many=True)},
    )
    def get(self, request, pk: int):
        links = (
            _student(pk)
            .access_links.filter(revoked_at__isnull=True)
            .select_related("user")
        )
        return ApiResponse.success(data=LinkedLoginSerializer(links, many=True).data)

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Give a login access (existing user_id, or a new_login to create + invite)",
        request=AccessCreateSerializer,
        responses={
            201: StudentDetailSerializer,
            400: OpenApiResponse(description="NOT_A_PORTAL_LOGIN"),
            409: OpenApiResponse(description="ACCESS_ALREADY_GRANTED / CONTACT_IN_USE"),
        },
    )
    def post(self, request, pk: int):
        serializer = AccessCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = _student(pk)
        user, invite = grant_access(
            actor=request.user,
            student=student,
            user=serializer.validated_data.get("user_id"),
            new_login=serializer.validated_data.get("new_login"),
            ip=client_ip(request),
        )
        return ApiResponse.created(
            message="Access granted.",
            data={
                "student": _detail(student),
                "user_id": user.pk,
                "invite_sent": invite,
            },
        )


class AdminStudentAccessRevokeView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Remove a login's access (the login itself stays)",
        request=None,
        responses={
            200: StudentDetailSerializer,
            404: OpenApiResponse(description="NOT_FOUND"),
        },
    )
    def delete(self, request, pk: int, user_id: int):
        student = _student(pk)
        user = get_object_or_404(User.all_objects, pk=user_id)
        revoke_access(
            actor=request.user, student=student, user=user, ip=client_ip(request)
        )
        return ApiResponse.success(message="Access removed.", data=_detail(student))


# ─────────────────────────────────────────────────────────────
# Portal
# ─────────────────────────────────────────────────────────────
def _sid(request) -> str | None:
    return request.auth.get(SID_CLAIM) if request.auth is not None else None


class PortalStudentListView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary='My students (the "Who\'s studying?" picker)',
        responses={200: PortalStudentSerializer(many=True)},
    )
    def get(self, request):
        context = {
            "selected_student_id": selected_student_id(
                user=request.user, session_id=_sid(request)
            )
        }
        students = linked_students(request.user)
        return ApiResponse.success(
            data=PortalStudentSerializer(students, many=True, context=context).data
        )


class PortalStudentDetailView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="One of my students",
        responses={
            200: PortalStudentSerializer,
            404: OpenApiResponse(description="Not linked to this login"),
        },
    )
    def get(self, request, pk: int):
        student = get_linked_student(request.user, pk)
        context = {
            "selected_student_id": selected_student_id(
                user=request.user, session_id=_sid(request)
            )
        }
        return ApiResponse.success(
            data=PortalStudentSerializer(student, context=context).data
        )


class PortalStudentSelectView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="Remember this student on this device",
        description="Convenience only: every request still checks access to the student.",
        request=None,
        responses={200: OpenApiResponse(description="Selected.")},
    )
    def post(self, request, pk: int):
        student = get_linked_student(request.user, pk)
        select_student(user=request.user, session_id=_sid(request), student=student)
        return ApiResponse.success(
            message="Selected.", data={"selected_student_id": student.pk}
        )


# ─────────────────────────────────────────────────────────────
# Photo
# ─────────────────────────────────────────────────────────────
class PhotoUploadSerializer(serializers.Serializer):
    photo = serializers.FileField(
        help_text="JPEG, PNG or WebP. Stored as a resized JPEG."
    )


class AdminStudentPhotoView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="View the student's photo",
        responses={(200, "image/jpeg"): OpenApiTypes.BINARY},
    )
    def get(self, request, pk: int):
        return photo_response(_student(pk))

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Upload / replace the student's photo",
        request={"multipart/form-data": PhotoUploadSerializer},
        responses={
            200: StudentDetailSerializer,
            400: OpenApiResponse(description="INVALID_PHOTO / PHOTO_TOO_LARGE"),
        },
    )
    def post(self, request, pk: int):
        serializer = PhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = set_photo(
            actor=request.user,
            student=_student(pk),
            upload=serializer.validated_data["photo"],
            ip=client_ip(request),
        )
        return ApiResponse.success(message="Photo saved.", data=_detail(student))

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Remove the student's photo",
        request=None,
        responses={200: StudentDetailSerializer},
    )
    def delete(self, request, pk: int):
        student = remove_photo(
            actor=request.user, student=_student(pk), ip=client_ip(request)
        )
        return ApiResponse.success(message="Photo removed.", data=_detail(student))


class PortalStudentPhotoView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="My student's photo",
        responses={(200, "image/jpeg"): OpenApiTypes.BINARY},
    )
    def get(self, request, pk: int):
        return photo_response(get_linked_student(request.user, pk))
