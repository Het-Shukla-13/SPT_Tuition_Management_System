"""
Administrator endpoints for managing user accounts: /api/v1/admin/users/.

Everything here requires role=ADMIN; changing roles additionally requires
the owner (superuser) account. Decisions live in services/users.py.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import (
    AdminContactSerializer,
    AdminUserSerializer,
    InviteResultSerializer,
    InviteUserSerializer,
    NameUpdateSerializer,
    RoleChangeSerializer,
)
from apps.accounts.services.contact import admin_set_contact
from apps.accounts.services.users import (
    activate_user,
    change_role,
    deactivate_user,
    invite_user,
    resend_invite,
    update_user_details,
)
from apps.common.permissions import IsAdmin, IsSuperUser
from apps.common.request_utils import client_ip
from apps.common.responses import ApiResponse

ADMIN_USERS_TAG = ["Admin: users"]


def _get_user(pk: int) -> User:
    # Soft-deleted users are hidden by the default manager, so they 404.
    return get_object_or_404(User.objects.all(), pk=pk)


@extend_schema(tags=ADMIN_USERS_TAG)
class AdminUserListView(generics.ListAPIView):
    """
    ?search=   email or phone (partial)
    ?role=     ADMIN | TEACHER | PORTAL
    ?is_active=true | false
    ?ordering= created_at | -created_at | email | last_login (prefix - for descending)
    ?page= & ?page_size= (max 100)
    """

    permission_classes = [IsAdmin]
    serializer_class = AdminUserSerializer
    queryset = User.objects.all()
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "phone"]
    ordering_fields = ["created_at", "email", "last_login"]
    ordering = ["-created_at"]

    @extend_schema(summary="List users")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create a login (invite)",
        description=(
            "Invite-only: this is the ONLY way accounts are created. The person gets an "
            "invite by SMS and/or email and logs in with a one-time code (or Google). "
            "Only the owner can create ADMIN logins."
        ),
        request=InviteUserSerializer,
        responses={
            201: InviteResultSerializer,
            400: OpenApiResponse(description="VALIDATION_ERROR"),
            403: OpenApiResponse(description="OWNER_REQUIRED (creating an ADMIN)"),
            409: OpenApiResponse(description="CONTACT_IN_USE"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = InviteUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, sent = invite_user(
            actor=request.user, **serializer.validated_data, ip=client_ip(request)
        )
        return ApiResponse.created(
            message="Login created and invite sent.",
            data={"user": AdminUserSerializer(user).data, "invite_sent": sent},
        )


class AdminUserDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_USERS_TAG, summary="Get a user", responses={200: AdminUserSerializer}
    )
    def get(self, request, pk: int):
        return ApiResponse.success(data=AdminUserSerializer(_get_user(pk)).data)

    @extend_schema(
        tags=ADMIN_USERS_TAG,
        summary="Edit a user's name",
        request=NameUpdateSerializer,
        responses={
            200: AdminUserSerializer,
            403: OpenApiResponse(description="OWNER_REQUIRED"),
        },
    )
    def patch(self, request, pk: int):
        serializer = NameUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = update_user_details(
            actor=request.user,
            target=_get_user(pk),
            first_name=serializer.validated_data.get("first_name"),
            last_name=serializer.validated_data.get("last_name"),
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Updated.", data=AdminUserSerializer(user).data
        )


class AdminUserResendInviteView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_USERS_TAG,
        summary="Resend the invite (before their first login)",
        request=None,
        responses={
            200: OpenApiResponse(description="Invite re-sent."),
            400: OpenApiResponse(description="INVITE_ALREADY_ACCEPTED"),
            403: OpenApiResponse(description="ACCOUNT_DISABLED"),
        },
    )
    def post(self, request, pk: int):
        sent = resend_invite(actor=request.user, target=_get_user(pk))
        return ApiResponse.success(
            message="Invite re-sent.", data={"invite_sent": sent}
        )


class AdminUserDeactivateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_USERS_TAG,
        summary="Deactivate a user (ends all their sessions)",
        description=(
            "The user can no longer log in and every device is logged out immediately. "
            "Their records (fees, tests, history) are untouched. Idempotent."
        ),
        request=None,
        responses={
            200: AdminUserSerializer,
            403: OpenApiResponse(
                description="CANNOT_MODIFY_SELF / OWNER_REQUIRED / PERMISSION_DENIED"
            ),
            409: OpenApiResponse(description="LAST_ADMIN"),
        },
    )
    def post(self, request, pk: int):
        user = deactivate_user(
            actor=request.user, target=_get_user(pk), ip=client_ip(request)
        )
        return ApiResponse.success(
            message="User deactivated.", data=AdminUserSerializer(user).data
        )


class AdminUserActivateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_USERS_TAG,
        summary="Reactivate a user",
        request=None,
        responses={
            200: AdminUserSerializer,
            403: OpenApiResponse(
                description="CANNOT_MODIFY_SELF / OWNER_REQUIRED / PERMISSION_DENIED"
            ),
        },
    )
    def post(self, request, pk: int):
        user = activate_user(
            actor=request.user, target=_get_user(pk), ip=client_ip(request)
        )
        return ApiResponse.success(
            message="User activated.", data=AdminUserSerializer(user).data
        )


class AdminUserContactView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_USERS_TAG,
        summary="Set or remove a user's email/phone (lost-access recovery)",
        description=(
            "For a user who lost access to their email/phone. The new value is saved "
            "UNVERIFIED and becomes verified on their first OTP login with it. The old "
            "address is notified. `identifier: null` removes it (only if the other remains)."
        ),
        request=AdminContactSerializer,
        responses={
            200: AdminUserSerializer,
            400: OpenApiResponse(
                description="VALIDATION_ERROR / CONTACT_UNCHANGED / CONTACT_NOT_SET / LAST_CONTACT_METHOD"
            ),
            403: OpenApiResponse(
                description="CANNOT_MODIFY_SELF / OWNER_REQUIRED / PERMISSION_DENIED"
            ),
            409: OpenApiResponse(description="CONTACT_IN_USE"),
        },
    )
    def post(self, request, pk: int):
        serializer = AdminContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = admin_set_contact(
            actor=request.user,
            target=_get_user(pk),
            channel=serializer.validated_data["channel"],
            identifier=serializer.validated_data["identifier"],
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Contact details updated.", data=AdminUserSerializer(user).data
        )


class AdminUserRoleView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        tags=ADMIN_USERS_TAG,
        summary="Change a user's role (owner account only)",
        description=(
            "Grants or revokes ADMIN. Only the owner (superuser) account may do this. "
            "The user's sessions all end, so the new role applies everywhere at once."
        ),
        request=RoleChangeSerializer,
        responses={
            200: AdminUserSerializer,
            403: OpenApiResponse(description="CANNOT_MODIFY_SELF / PERMISSION_DENIED"),
            409: OpenApiResponse(description="LAST_ADMIN"),
        },
    )
    def post(self, request, pk: int):
        serializer = RoleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = change_role(
            actor=request.user,
            target=_get_user(pk),
            role=serializer.validated_data["role"],
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Role updated.", data=AdminUserSerializer(user).data
        )
