from django.urls import path

from apps.accounts.views.account import (
    ContactChangeView,
    ContactRemoveView,
    ContactVerifyView,
)
from apps.accounts.views.auth import (
    LogoutAllView,
    LogoutView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    SessionListView,
    SessionRevokeView,
    TokenRefreshView,
)
from apps.accounts.views.google import (
    GoogleSignInView,
    GoogleUnlinkView,
    GoogleVerifyView,
)
from apps.accounts.views.password import (
    LoginResendView,
    LoginVerifyView,
    LoginView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    TrustedDeviceListView,
    TrustedDeviceRevokeView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("login/verify/", LoginVerifyView.as_view(), name="auth-login-verify"),
    path("login/resend/", LoginResendView.as_view(), name="auth-login-resend"),
    path(
        "password/reset/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset",
    ),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
    path("devices/", TrustedDeviceListView.as_view(), name="auth-devices"),
    path(
        "devices/<int:pk>/",
        TrustedDeviceRevokeView.as_view(),
        name="auth-device-revoke",
    ),
    path("me/contact/", ContactChangeView.as_view(), name="auth-contact-change"),
    path("me/contact/verify/", ContactVerifyView.as_view(), name="auth-contact-verify"),
    path(
        "me/contact/<str:kind>/",
        ContactRemoveView.as_view(),
        name="auth-contact-remove",
    ),
    path("google/", GoogleSignInView.as_view(), name="auth-google"),
    path("google/verify/", GoogleVerifyView.as_view(), name="auth-google-verify"),
    path("google/unlink/", GoogleUnlinkView.as_view(), name="auth-google-unlink"),
    path("otp/request/", OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("logout-all/", LogoutAllView.as_view(), name="auth-logout-all"),
    path("sessions/", SessionListView.as_view(), name="auth-sessions"),
    path("sessions/<int:pk>/", SessionRevokeView.as_view(), name="auth-session-revoke"),
    path("me/", MeView.as_view(), name="auth-me"),
]
