"""
Staff (admins + teachers):
  /api/v1/staff/tests/            archive: list/search/filter, upload, edit, replace PDF,
  /api/v1/staff/notes/            archive, download, assign, list assignments
  /api/v1/staff/test-assignments/ list/filter, update test time, grade, bulk revoke
  /api/v1/staff/note-assignments/ list/filter, bulk revoke
Portal (parents / students), only for linked + ACTIVE students:
  /api/v1/portal/students/{student_id}/tests/...   /notes/...
"""

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView

from apps.common.permissions import IsPortalUser, IsStaff
from apps.common.request_utils import client_ip
from apps.common.responses import ApiResponse
from apps.learning import services
from apps.learning.models import (
    DocumentFile,
    Note,
    NoteAssignment,
    TestAssignment,
    TestPaper,
)
from apps.learning.serializers import (
    ArchiveSerializer,
    AssignNoteSerializer,
    AssignTestSerializer,
    DocumentFileSerializer,
    GradeSerializer,
    NoteAssignmentSerializer,
    NoteCreateSerializer,
    NoteSerializer,
    NoteWriteSerializer,
    PortalNoteSerializer,
    PortalTestSerializer,
    ReplaceFileSerializer,
    RevokeSerializer,
    TestAssignmentSerializer,
    TestAssignmentUpdateSerializer,
    TestPaperCreateSerializer,
    TestPaperSerializer,
    TestPaperWriteSerializer,
)

INLINE_PARAM = OpenApiParameter(
    "inline",
    OpenApiTypes.BOOL,
    description="true = open in the browser, false = download.",
)


def _inline(request) -> bool:
    return request.query_params.get("inline", "true").lower() != "false"


# ─────────────────────────────────────────────────────────────
# Staff: archive items (shared base for tests and notes)
# ─────────────────────────────────────────────────────────────
class _ItemViewSet(viewsets.GenericViewSet):
    permission_classes = [IsStaff]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    main_kind: str
    read_serializer = write_serializer = create_serializer = assign_serializer = None
    search_fields = ["title", "description", "subject__name", "chapters__name"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        return self.read_serializer

    def get_queryset(self):
        queryset = (
            self.queryset.select_related(
                "board", "standard", "subject", "academic_year"
            )
            .prefetch_related(
                "chapters",
                Prefetch(
                    "files",
                    queryset=DocumentFile.objects.filter(is_current=True),
                    to_attr="current_files",
                ),
            )
            .annotate(
                active_assignment_count=Count(
                    "assignments",
                    filter=Q(assignments__revoked_at__isnull=True),
                    distinct=True,
                )
            )
        )
        if self.action == "list":
            archived = (
                self.request.query_params.get("is_archived", "false").lower() == "true"
            )
            queryset = queryset.filter(is_archived=archived)
        if self.request.query_params.get("search"):
            queryset = queryset.distinct()  # chapter join may duplicate rows
        return queryset

    def _item(self, pk):
        return get_object_or_404(self.queryset, pk=pk)

    def list(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response(self.read_serializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        return ApiResponse.success(data=self.read_serializer(self._item(pk)).data)

    def create(self, request):
        serializer = self.create_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        confirm_duplicate = data.pop("confirm_duplicate", False)
        files = {self.main_kind: data.pop("file")}
        if "answer_key" in data:
            files[DocumentFile.Kind.ANSWER_KEY] = data.pop("answer_key")
        item = services.create_item(
            actor=request.user,
            model=self.queryset.model,
            data=data,
            files=files,
            confirm_duplicate=confirm_duplicate,
            ip=client_ip(request),
        )
        return ApiResponse.created(
            message="Uploaded.", data=self.read_serializer(item).data
        )

    def partial_update(self, request, pk=None):
        item = self._item(pk)
        serializer = self.write_serializer(
            instance=item, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        item = services.update_item(
            actor=request.user,
            item=item,
            data=dict(serializer.validated_data),
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Updated.", data=self.read_serializer(item).data
        )

    def _replace(self, request, pk, kind):
        serializer = ReplaceFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = services.replace_file(
            actor=request.user,
            item=self._item(pk),
            kind=kind,
            upload=serializer.validated_data["file"],
            confirm_duplicate=serializer.validated_data["confirm_duplicate"],
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="PDF replaced.", data=DocumentFileSerializer(doc).data
        )

    @extend_schema(request=ArchiveSerializer, summary="Archive / unarchive")
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        serializer = ArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = services.set_archived(
            actor=request.user,
            item=self._item(pk),
            archived=serializer.validated_data["archived"],
            ip=client_ip(request),
        )
        return ApiResponse.success(data=self.read_serializer(item).data)

    @extend_schema(
        summary="Versions of the PDF(s)",
        responses={200: DocumentFileSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        return ApiResponse.success(
            data=DocumentFileSerializer(self._item(pk).files.all(), many=True).data
        )

    def _download(self, request, pk, kind):
        version = request.query_params.get("version")
        files = self._item(pk).files.filter(kind=kind)
        doc = (
            files.filter(version=version).first()
            if version
            else files.filter(is_current=True).first()
        )
        if doc is None:
            return ApiResponse.error(
                "No such file.", error_code="NOT_FOUND", status_code=404
            )
        return services.file_response(
            doc, inline=_inline(request), actor=request.user, ip=client_ip(request)
        )

    def _assign(self, request, pk, extra_fields):
        serializer = self.assign_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        extra = {f: data[f] for f in extra_fields if data.get(f) is not None}
        extra["remarks"] = data["remarks"]
        result = services.assign(
            actor=request.user,
            item=self._item(pk),
            student_ids=data["student_ids"],
            extra=extra,
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message=f"Assigned to {len(result['assigned'])}, failed for {len(result['failed'])}.",
            data=result,
        )


TESTS_TAG, NOTES_TAG = ["Staff: test papers"], ["Staff: notes"]


@extend_schema_view(
    list=extend_schema(tags=TESTS_TAG, summary="Test archive (search / filter / sort)"),
    retrieve=extend_schema(tags=TESTS_TAG, summary="Get a test paper"),
    create=extend_schema(
        tags=TESTS_TAG,
        summary="Upload a test paper (+ optional answer key)",
        request=TestPaperCreateSerializer,
    ),
    partial_update=extend_schema(
        tags=TESTS_TAG, summary="Edit details", request=TestPaperWriteSerializer
    ),
    archive=extend_schema(tags=TESTS_TAG),
    versions=extend_schema(tags=TESTS_TAG),
)
class TestPaperViewSet(_ItemViewSet):
    queryset = TestPaper.objects.all()
    main_kind = DocumentFile.Kind.PAPER
    read_serializer, write_serializer = TestPaperSerializer, TestPaperWriteSerializer
    create_serializer, assign_serializer = (
        TestPaperCreateSerializer,
        AssignTestSerializer,
    )
    filterset_fields = [
        "board",
        "standard",
        "subject",
        "semester",
        "academic_year",
        "chapters",
        "school",
    ]
    ordering_fields = [*_ItemViewSet.ordering_fields, "test_date"]

    @extend_schema(
        tags=TESTS_TAG,
        summary="Replace the test paper PDF (new version)",
        request=ReplaceFileSerializer,
    )
    @action(detail=True, methods=["post"], url_path="paper")
    def replace_paper(self, request, pk=None):
        return self._replace(request, pk, DocumentFile.Kind.PAPER)

    @extend_schema(
        tags=TESTS_TAG,
        summary="Upload / replace the answer key",
        request=ReplaceFileSerializer,
    )
    @action(detail=True, methods=["post"], url_path="answer-key")
    def answer_key(self, request, pk=None):
        return self._replace(request, pk, DocumentFile.Kind.ANSWER_KEY)

    @extend_schema(tags=TESTS_TAG, summary="Remove the answer key", request=None)
    @answer_key.mapping.delete
    def delete_answer_key(self, request, pk=None):
        services.remove_answer_key(
            actor=request.user, paper=self._item(pk), ip=client_ip(request)
        )
        return ApiResponse.success(message="Answer key removed.")

    @extend_schema(
        tags=TESTS_TAG,
        summary="Open / download a PDF",
        parameters=[
            OpenApiParameter("kind", OpenApiTypes.STR, enum=["PAPER", "ANSWER_KEY"]),
            OpenApiParameter(
                "version", OpenApiTypes.INT, description="Default: current."
            ),
            INLINE_PARAM,
        ],
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        kind = request.query_params.get("kind", DocumentFile.Kind.PAPER)
        if kind not in (DocumentFile.Kind.PAPER, DocumentFile.Kind.ANSWER_KEY):
            return ApiResponse.error(
                "kind must be PAPER or ANSWER_KEY.", error_code="VALIDATION_ERROR"
            )
        return self._download(request, pk, kind)

    @extend_schema(
        tags=TESTS_TAG,
        summary="Assign to students (bulk; reports per-student failures)",
        request=AssignTestSerializer,
        responses={
            200: OpenApiResponse(
                description='{"assigned": [...], "failed": [{"student_id", "reason"}]}'
            )
        },
    )
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        return self._assign(request, pk, ("test_starts_at", "duration_minutes"))


@extend_schema_view(
    list=extend_schema(
        tags=NOTES_TAG, summary="Notes archive (search / filter / sort)"
    ),
    retrieve=extend_schema(tags=NOTES_TAG, summary="Get notes"),
    create=extend_schema(
        tags=NOTES_TAG, summary="Upload notes", request=NoteCreateSerializer
    ),
    partial_update=extend_schema(
        tags=NOTES_TAG, summary="Edit details", request=NoteWriteSerializer
    ),
    archive=extend_schema(tags=NOTES_TAG),
    versions=extend_schema(tags=NOTES_TAG),
)
class NoteViewSet(_ItemViewSet):
    queryset = Note.objects.all()
    main_kind = DocumentFile.Kind.NOTE
    read_serializer, write_serializer = NoteSerializer, NoteWriteSerializer
    create_serializer, assign_serializer = NoteCreateSerializer, AssignNoteSerializer
    filterset_fields = [
        "board",
        "standard",
        "subject",
        "semester",
        "academic_year",
        "chapters",
    ]

    @extend_schema(
        tags=NOTES_TAG,
        summary="Replace the notes PDF (new version)",
        request=ReplaceFileSerializer,
    )
    @action(detail=True, methods=["post"], url_path="file")
    def replace_file(self, request, pk=None):
        return self._replace(request, pk, DocumentFile.Kind.NOTE)

    @extend_schema(
        tags=NOTES_TAG,
        summary="Open / download the PDF",
        parameters=[OpenApiParameter("version", OpenApiTypes.INT), INLINE_PARAM],
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        return self._download(request, pk, DocumentFile.Kind.NOTE)

    @extend_schema(
        tags=NOTES_TAG,
        summary="Assign to students (bulk)",
        request=AssignNoteSerializer,
        responses={200: OpenApiResponse(description="assigned / failed lists")},
    )
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        return self._assign(request, pk, ())


# ─────────────────────────────────────────────────────────────
# Staff: assignments
# ─────────────────────────────────────────────────────────────
class _AssignmentListMixin(generics.GenericAPIView):
    permission_classes = [IsStaff]
    ordering = ["-assigned_at"]

    def filter_active(self, queryset):
        status = self.request.query_params.get("status", "active")
        if status == "active":
            return queryset.filter(revoked_at__isnull=True)
        if status == "revoked":
            return queryset.filter(revoked_at__isnull=False)
        return queryset  # "all"


@extend_schema(tags=["Staff: test assignments"])
class TestAssignmentListView(_AssignmentListMixin, generics.ListAPIView):
    """?student= ?test_paper= ?status=active|revoked|all (default active)"""

    serializer_class = TestAssignmentSerializer
    filterset_fields = ["student", "test_paper"]

    def get_queryset(self):
        return self.filter_active(
            TestAssignment.objects.select_related("student", "test_paper")
        )

    @extend_schema(summary="List test assignments")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema(tags=["Staff: note assignments"])
class NoteAssignmentListView(_AssignmentListMixin, generics.ListAPIView):
    """?student= ?note= ?status=active|revoked|all (default active)"""

    serializer_class = NoteAssignmentSerializer
    filterset_fields = ["student", "note"]

    def get_queryset(self):
        return self.filter_active(
            NoteAssignment.objects.select_related("student", "note")
        )

    @extend_schema(summary="List note assignments")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TestAssignmentDetailView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["Staff: test assignments"],
        summary="Change test time / duration / remarks",
        request=TestAssignmentUpdateSerializer,
        responses={200: TestAssignmentSerializer},
    )
    def patch(self, request, pk: int):
        serializer = TestAssignmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = services.update_test_assignment(
            actor=request.user,
            assignment=get_object_or_404(TestAssignment, pk=pk),
            data=serializer.validated_data,
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Updated.", data=TestAssignmentSerializer(assignment).data
        )


class TestAssignmentGradeView(APIView):
    permission_classes = [IsStaff]

    @extend_schema(
        tags=["Staff: test assignments"],
        summary="Enter marks",
        request=GradeSerializer,
        responses={200: TestAssignmentSerializer},
    )
    def post(self, request, pk: int):
        serializer = GradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.grade(
            actor=request.user,
            assignment=get_object_or_404(TestAssignment, pk=pk),
            marks=serializer.validated_data["marks_obtained"],
            remarks=serializer.validated_data["grade_remarks"],
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Marks saved.", data=TestAssignmentSerializer(assignment).data
        )


class _RevokeView(APIView):
    permission_classes = [IsStaff]
    model = None

    def post(self, request):
        serializer = RevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.revoke(
            actor=request.user,
            model=self.model,
            assignment_ids=serializer.validated_data["assignment_ids"],
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message=f"Revoked {len(result['revoked'])}, failed {len(result['failed'])}.",
            data=result,
        )


class TestAssignmentRevokeView(_RevokeView):
    model = TestAssignment

    @extend_schema(
        tags=["Staff: test assignments"],
        summary="Revoke (bulk; history kept)",
        request=RevokeSerializer,
        responses={
            200: OpenApiResponse(description='{"revoked": [...], "failed": [...]}')
        },
    )
    def post(self, request):
        return super().post(request)


class NoteAssignmentRevokeView(_RevokeView):
    model = NoteAssignment

    @extend_schema(
        tags=["Staff: note assignments"],
        summary="Revoke (bulk; history kept)",
        request=RevokeSerializer,
        responses={
            200: OpenApiResponse(description='{"revoked": [...], "failed": [...]}')
        },
    )
    def post(self, request):
        return super().post(request)


# ─────────────────────────────────────────────────────────────
# Portal
# ─────────────────────────────────────────────────────────────
PORTAL_TAG = ["Portal: tests & notes"]


class PortalTestListView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="My student's assigned tests (upcoming and past)",
        responses={200: PortalTestSerializer(many=True)},
    )
    def get(self, request, student_id: int):
        student = services.portal_student(request.user, student_id)
        assignments = services.portal_test_assignments(student).prefetch_related(
            "test_paper__chapters"
        )
        return ApiResponse.success(
            data=PortalTestSerializer(assignments, many=True).data
        )


class PortalTestDetailView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="One assigned test",
        responses={200: PortalTestSerializer},
    )
    def get(self, request, student_id: int, pk: int):
        student = services.portal_student(request.user, student_id)
        assignment = get_object_or_404(services.portal_test_assignments(student), pk=pk)
        return ApiResponse.success(data=PortalTestSerializer(assignment).data)


class PortalTestDownloadView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="Open / download the test paper or (after the test) the answer key",
        parameters=[
            OpenApiParameter("kind", OpenApiTypes.STR, enum=["PAPER", "ANSWER_KEY"]),
            INLINE_PARAM,
        ],
        responses={
            (200, "application/pdf"): OpenApiTypes.BINARY,
            403: OpenApiResponse(description="ANSWER_KEY_LOCKED (test not over yet)"),
            404: OpenApiResponse(description="Not assigned / ANSWER_KEY_UNAVAILABLE"),
        },
    )
    def get(self, request, student_id: int, pk: int):
        student = services.portal_student(request.user, student_id)
        assignment = get_object_or_404(services.portal_test_assignments(student), pk=pk)
        kind = request.query_params.get("kind", DocumentFile.Kind.PAPER)
        if kind not in (DocumentFile.Kind.PAPER, DocumentFile.Kind.ANSWER_KEY):
            return ApiResponse.error(
                "kind must be PAPER or ANSWER_KEY.", error_code="VALIDATION_ERROR"
            )
        doc = services.portal_test_file(assignment, kind)
        return services.file_response(
            doc, inline=_inline(request), actor=request.user, ip=client_ip(request)
        )


class PortalNoteListView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="My student's notes (search / filter)",
        parameters=[
            OpenApiParameter(
                "search", OpenApiTypes.STR, description="Title, subject or chapter."
            ),
            OpenApiParameter("subject", OpenApiTypes.INT),
            OpenApiParameter("chapter", OpenApiTypes.INT),
        ],
        responses={200: PortalNoteSerializer(many=True)},
    )
    def get(self, request, student_id: int):
        student = services.portal_student(request.user, student_id)
        notes = services.portal_note_assignments(student).prefetch_related(
            "note__chapters"
        )
        params = request.query_params
        if params.get("subject"):
            notes = notes.filter(note__subject_id=params["subject"])
        if params.get("chapter"):
            notes = notes.filter(note__chapters__id=params["chapter"])
        if params.get("search"):
            term = params["search"]
            notes = notes.filter(
                Q(note__title__icontains=term)
                | Q(note__subject__name__icontains=term)
                | Q(note__chapters__name__icontains=term)
            )
        return ApiResponse.success(
            data=PortalNoteSerializer(notes.distinct(), many=True).data
        )


class PortalNoteDownloadView(APIView):
    permission_classes = [IsPortalUser]

    @extend_schema(
        tags=PORTAL_TAG,
        summary="Open / download notes",
        parameters=[INLINE_PARAM],
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request, student_id: int, pk: int):
        student = services.portal_student(request.user, student_id)
        assignment = get_object_or_404(services.portal_note_assignments(student), pk=pk)
        doc = services.current_file(assignment.note, DocumentFile.Kind.NOTE)
        if doc is None:
            return ApiResponse.error(
                "No file.", error_code="NOT_FOUND", status_code=404
            )
        return services.file_response(
            doc, inline=_inline(request), actor=request.user, ip=client_ip(request)
        )
