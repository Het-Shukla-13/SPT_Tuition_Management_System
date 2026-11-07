from django.urls import path

from apps.enquiries.views import (
    AdminEnquiryDetailView,
    AdminEnquiryListView,
    PublicEnquiryView,
)

public_urlpatterns = [path("", PublicEnquiryView.as_view(), name="public-enquiry")]
admin_urlpatterns = [
    path("", AdminEnquiryListView.as_view(), name="admin-enquiries"),
    path("<int:pk>/", AdminEnquiryDetailView.as_view(), name="admin-enquiry-detail"),
]
