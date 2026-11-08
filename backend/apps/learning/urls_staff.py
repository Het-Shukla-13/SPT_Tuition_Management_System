"""Mounted at /api/v1/staff/."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.learning.views import (
    NoteAssignmentListView,
    NoteAssignmentRevokeView,
    NoteViewSet,
    TestAssignmentDetailView,
    TestAssignmentGradeView,
    TestAssignmentListView,
    TestAssignmentRevokeView,
    TestPaperViewSet,
)

router = SimpleRouter()
router.register("tests", TestPaperViewSet, basename="staff-test")
router.register("notes", NoteViewSet, basename="staff-note")

urlpatterns = [
    path(
        "test-assignments/",
        TestAssignmentListView.as_view(),
        name="staff-test-assignments",
    ),
    path(
        "test-assignments/revoke/",
        TestAssignmentRevokeView.as_view(),
        name="staff-test-assignments-revoke",
    ),
    path(
        "test-assignments/<int:pk>/",
        TestAssignmentDetailView.as_view(),
        name="staff-test-assignment",
    ),
    path(
        "test-assignments/<int:pk>/grade/",
        TestAssignmentGradeView.as_view(),
        name="staff-test-assignment-grade",
    ),
    path(
        "note-assignments/",
        NoteAssignmentListView.as_view(),
        name="staff-note-assignments",
    ),
    path(
        "note-assignments/revoke/",
        NoteAssignmentRevokeView.as_view(),
        name="staff-note-assignments-revoke",
    ),
    *router.urls,
]
