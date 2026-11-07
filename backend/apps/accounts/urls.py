from django.urls import path

from apps.accounts.views import (
    LogoutView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    TokenRefreshEnvelopeView,
)

urlpatterns = [
    path("otp/request/", OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="auth-otp-verify"),
    path(
        "token/refresh/", TokenRefreshEnvelopeView.as_view(), name="auth-token-refresh"
    ),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
