"""Mounted at /api/v1/admin/students/."""

from django.urls import path

from apps.students.views import (
    AdminStudentAcademicView,
    AdminStudentAccessRevokeView,
    AdminStudentAccessView,
    AdminStudentDetailView,
    AdminStudentHistoryView,
    AdminStudentListView,
    AdminStudentPhotoView,
    AdminStudentStatusView,
    AdminStudentSubjectsView,
)

urlpatterns = [
    path("", AdminStudentListView.as_view(), name="admin-students"),
    path("<int:pk>/", AdminStudentDetailView.as_view(), name="admin-student-detail"),
    path(
        "<int:pk>/academic/",
        AdminStudentAcademicView.as_view(),
        name="admin-student-academic",
    ),
    path(
        "<int:pk>/history/",
        AdminStudentHistoryView.as_view(),
        name="admin-student-history",
    ),
    path(
        "<int:pk>/status/",
        AdminStudentStatusView.as_view(),
        name="admin-student-status",
    ),
    path(
        "<int:pk>/subjects/",
        AdminStudentSubjectsView.as_view(),
        name="admin-student-subjects",
    ),
    path(
        "<int:pk>/access/",
        AdminStudentAccessView.as_view(),
        name="admin-student-access",
    ),
    path(
        "<int:pk>/access/<int:user_id>/",
        AdminStudentAccessRevokeView.as_view(),
        name="admin-student-access-revoke",
    ),
    path(
        "<int:pk>/photo/", AdminStudentPhotoView.as_view(), name="admin-student-photo"
    ),
]
