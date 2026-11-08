from django.urls import path

from apps.dashboard.views import PortalOverviewView, StaffDashboardView

staff_urlpatterns = [
    path("dashboard/", StaffDashboardView.as_view(), name="staff-dashboard")
]
portal_urlpatterns = [
    path("overview/", PortalOverviewView.as_view(), name="portal-overview")
]
