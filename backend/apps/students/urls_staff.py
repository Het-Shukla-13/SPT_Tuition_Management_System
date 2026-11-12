"""Mounted at /api/v1/staff/students/."""

from django.urls import path

from apps.students.views_staff import StaffStudentLookupView

urlpatterns = [
    path("", StaffStudentLookupView.as_view(), name="staff-students"),
]
