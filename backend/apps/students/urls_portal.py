"""Mounted at /api/v1/portal/students/."""

from django.urls import path

from apps.students.views import (
    PortalStudentDetailView,
    PortalStudentListView,
    PortalStudentPhotoView,
    PortalStudentSelectView,
)

urlpatterns = [
    path("", PortalStudentListView.as_view(), name="portal-students"),
    path("<int:pk>/", PortalStudentDetailView.as_view(), name="portal-student-detail"),
    path(
        "<int:pk>/select/",
        PortalStudentSelectView.as_view(),
        name="portal-student-select",
    ),
    path(
        "<int:pk>/photo/", PortalStudentPhotoView.as_view(), name="portal-student-photo"
    ),
]
