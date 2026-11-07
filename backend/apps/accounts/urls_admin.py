"""Administrator user-management routes, mounted at /api/v1/admin/users/."""

from django.urls import path

from apps.accounts.views.users import (
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserDetailView,
    AdminUserListView,
    AdminUserRoleView,
)

urlpatterns = [
    path("", AdminUserListView.as_view(), name="admin-users"),
    path("<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path(
        "<int:pk>/deactivate/",
        AdminUserDeactivateView.as_view(),
        name="admin-user-deactivate",
    ),
    path(
        "<int:pk>/activate/",
        AdminUserActivateView.as_view(),
        name="admin-user-activate",
    ),
    path("<int:pk>/role/", AdminUserRoleView.as_view(), name="admin-user-role"),
]
