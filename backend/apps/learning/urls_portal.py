"""Mounted at /api/v1/portal/students/<student_id>/."""

from django.urls import path

from apps.learning.views import (
    PortalNoteDownloadView,
    PortalNoteListView,
    PortalTestDetailView,
    PortalTestDownloadView,
    PortalTestListView,
)

urlpatterns = [
    path("tests/", PortalTestListView.as_view(), name="portal-tests"),
    path("tests/<int:pk>/", PortalTestDetailView.as_view(), name="portal-test"),
    path(
        "tests/<int:pk>/download/",
        PortalTestDownloadView.as_view(),
        name="portal-test-download",
    ),
    path("notes/", PortalNoteListView.as_view(), name="portal-notes"),
    path(
        "notes/<int:pk>/download/",
        PortalNoteDownloadView.as_view(),
        name="portal-note-download",
    ),
]
