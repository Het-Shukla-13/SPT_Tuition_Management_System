"""
Root URL configuration.

All API routes live under /api/v1/ so a future breaking change can ship
as /api/v2/ without disturbing existing clients.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1_patterns = [
    path("", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("admin/users/", include("apps.accounts.urls_admin")),
    path("academics/", include("apps.academics.urls")),
    path("admin/students/", include("apps.students.urls_admin")),
    path("portal/students/", include("apps.students.urls_portal")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
]

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="api-schema"),
            name="api-docs",
        ),
    ]
