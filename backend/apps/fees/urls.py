from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.fees import views

router = SimpleRouter()
router.register("fee-structures", views.FeeStructureViewSet, basename="fee-structure")

# Mounted at /api/v1/admin/
admin_urlpatterns = [
    path("fees/accounts/", views.FeeAccountListView.as_view(), name="fee-accounts"),
    path(
        "fees/accounts/<int:pk>/",
        views.FeeAccountDetailView.as_view(),
        name="fee-account",
    ),
    path(
        "fees/accounts/<int:pk>/payments/",
        views.PaymentCreateView.as_view(),
        name="fee-payment",
    ),
    path(
        "fees/accounts/<int:pk>/adjustments/",
        views.AdjustmentCreateView.as_view(),
        name="fee-adjustment",
    ),
    path(
        "fees/accounts/<int:pk>/agreed-fee/",
        views.AgreedFeeView.as_view(),
        name="fee-agreed",
    ),
    path(
        "fees/accounts/<int:pk>/refunds/",
        views.RefundCreateView.as_view(),
        name="fee-refund",
    ),
    path(
        "fees/entries/<int:entry_id>/reverse/",
        views.ReversePaymentView.as_view(),
        name="fee-reverse",
    ),
    path("fees/payments/", views.PaymentListView.as_view(), name="fee-payments"),
    path(
        "fees/payments/<int:entry_id>/receipt/",
        views.ReceiptView.as_view(),
        name="fee-receipt",
    ),
    path(
        "fees/students/<int:student_id>/accounts/",
        views.StudentFeeAccountsView.as_view(),
        name="fee-student-accounts",
    ),
    path(
        "rollover/preview/",
        views.RolloverPreviewView.as_view(),
        name="rollover-preview",
    ),
    path("rollover/apply/", views.RolloverApplyView.as_view(), name="rollover-apply"),
    *router.urls,
]

# Mounted at /api/v1/portal/students/<student_id>/
portal_urlpatterns = [
    path("fees/", views.PortalFeesView.as_view(), name="portal-fees"),
    path(
        "fees/receipts/<int:entry_id>/",
        views.PortalReceiptView.as_view(),
        name="portal-fee-receipt",
    ),
]
