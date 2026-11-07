"""
Reference data API: /api/v1/academics/...

- Any logged-in user can read ACTIVE items (needed for filters and forms).
- Admins can also see inactive items (?is_active=false) and create/update.
- No DELETE: deactivate with PATCH {"is_active": false} instead.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated

from apps.academics.models import (
    AcademicYear,
    Board,
    Chapter,
    School,
    Standard,
    Subject,
)
from apps.academics.serializers import (
    AcademicYearSerializer,
    BoardSerializer,
    ChapterSerializer,
    SchoolSerializer,
    StandardSerializer,
    SubjectSerializer,
)
from apps.common.permissions import IsAdmin, has_role
from apps.common.viewsets import EnvelopeModelViewSet


class _ReferenceViewSet(EnvelopeModelViewSet):
    read_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_actions:
            return [IsAuthenticated()]
        return [IsAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not has_role(self.request.user, "ADMIN"):
            queryset = queryset.filter(is_active=True)
        return queryset


def _docs(name: str, tag: str):
    return extend_schema_view(
        list=extend_schema(tags=[tag], summary=f"List {name}"),
        retrieve=extend_schema(tags=[tag], summary=f"Get one {name[:-1]}"),
        create=extend_schema(tags=[tag], summary=f"Create {name[:-1]} (admin)"),
        partial_update=extend_schema(
            tags=[tag], summary=f"Update / deactivate {name[:-1]} (admin)"
        ),
    )


TAG = "Academics"


@_docs("boards", TAG)
class BoardViewSet(_ReferenceViewSet):
    queryset = Board.objects.all()
    serializer_class = BoardSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "name"]


@_docs("standards", TAG)
class StandardViewSet(_ReferenceViewSet):
    queryset = Standard.objects.all()
    serializer_class = StandardSerializer
    filterset_fields = ["is_active"]
    ordering_fields = ["level"]


@_docs("subjects", TAG)
class SubjectViewSet(_ReferenceViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["name"]


@_docs("chapters", TAG)
class ChapterViewSet(_ReferenceViewSet):
    queryset = Chapter.objects.select_related("board", "standard", "subject")
    serializer_class = ChapterSerializer
    filterset_fields = ["board", "standard", "subject", "is_active"]
    search_fields = ["name"]
    ordering_fields = ["number", "name"]


@_docs("schools", TAG)
class SchoolViewSet(_ReferenceViewSet):
    queryset = School.objects.select_related("board")
    serializer_class = SchoolSerializer
    filterset_fields = ["board", "city", "is_active"]
    search_fields = ["name", "city"]
    ordering_fields = ["name", "city"]


@_docs("academic years", TAG)
class AcademicYearViewSet(_ReferenceViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    filterset_fields = ["is_current", "is_active"]
    ordering_fields = ["start_date", "name"]
