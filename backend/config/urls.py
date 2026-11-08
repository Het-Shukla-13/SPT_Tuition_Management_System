"""
Root URL configuration.

All API routes live under /api/v1/ so a future breaking change can ship
as /api/v2/ without disturbing existing clients.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.enquiries.urls import admin_urlpatterns as enquiry_admin_urls
from apps.enquiries.urls import public_urlpatterns as enquiry_public_urls
from apps.fees.urls import admin_urlpatterns as fees_admin_urls
from apps.fees.urls import portal_urlpatterns as fees_portal_urls

api_v1_patterns = [
    path("", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("admin/users/", include("apps.accounts.urls_admin")),
    path("academics/", include("apps.academics.urls")),
    path("admin/students/", include("apps.students.urls_admin")),
    path("portal/students/", include("apps.students.urls_portal")),
    path("portal/students/<int:student_id>/", include("apps.learning.urls_portal")),
    path("portal/students/<int:student_id>/", include(fees_portal_urls)),
    path("staff/", include("apps.learning.urls_staff")),
    path("admin/", include(fees_admin_urls)),
    path("public/enquiries/", include(enquiry_public_urls)),
    path("admin/enquiries/", include(enquiry_admin_urls)),
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
