"""
Public:  POST /api/v1/public/enquiries/   (no login; throttled; honeypot)
         GET  /api/v1/public/enquiries/options/  (boards + standards for the form)
Admin:   /api/v1/admin/enquiries/          (list, detail, update status/notes/student)
"""

import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.academics.models import Board, Standard
from apps.common.permissions import IsAdmin
from apps.common.request_utils import client_ip
from apps.common.responses import ApiResponse
from apps.common.throttling import ResilientScopedRateThrottle
from apps.enquiries.models import AdmissionEnquiry
from apps.enquiries.serializers import (
    AdminEnquirySerializer,
    EnquiryUpdateSerializer,
    PublicEnquirySerializer,
    StaffEnquirySerializer,
)
from apps.enquiries.services import record_enquiry, submit_enquiry, update_enquiry

logger = logging.getLogger(__name__)

THANKS = "Thank you! The institute will contact you soon."
ADMIN_TAG = ["Admin: enquiries"]


class PublicEnquiryView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ResilientScopedRateThrottle]  # fail closed: it emails admins
    throttle_scope = "enquiry"

    @extend_schema(
        tags=["Public"],
        summary="Admission enquiry (homepage form)",
        description="Stores the request for the institute to follow up. Never creates a login.",
        request=PublicEnquirySerializer,
        responses={
            201: OpenApiResponse(description="Received."),
            429: OpenApiResponse(description="THROTTLED"),
        },
    )
    def post(self, request):
        serializer = PublicEnquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if data.pop("website", ""):
            # Honeypot filled: a bot. Pretend success, store nothing.
            logger.info("Enquiry honeypot triggered from %s", client_ip(request))
            return ApiResponse.created(message=THANKS)
        submit_enquiry(data=data, ip=client_ip(request))
        return ApiResponse.created(message=THANKS)


class PublicEnquiryOptionsView(APIView):
    """Active boards and standards, so the public form can offer them without a login."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        summary="Choices for the admission enquiry form",
        responses={
            200: OpenApiResponse(
                description='{"boards": [{id, code, name}], "standards": [{id, name}]}'
            )
        },
    )
    def get(self, request):
        boards = Board.objects.filter(is_active=True).order_by("code")
        standards = Standard.objects.filter(is_active=True).order_by("level")
        return ApiResponse.success(
            data={
                "boards": list(boards.values("id", "code", "name")),
                "standards": list(standards.values("id", "name")),
            }
        )


@extend_schema(tags=ADMIN_TAG)
class AdminEnquiryListView(generics.ListAPIView):
    """?status=  ?source=  ?medium=  ?search=name/phone/email  ?ordering=created_at"""

    permission_classes = [IsAdmin]
    serializer_class = AdminEnquirySerializer
    queryset = AdmissionEnquiry.objects.select_related("standard", "board")
    filterset_fields = ["status", "source", "medium", "standard", "board"]
    search_fields = ["parent_name", "student_name", "phone", "email"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    @extend_schema(summary="List enquiries")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Record an enquiry (walk-in / phone / referral)",
        description="For families who came in or called. Never creates a login or a student.",
        request=StaffEnquirySerializer,
        responses={201: AdminEnquirySerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = StaffEnquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquiry = record_enquiry(
            actor=request.user,
            data=dict(serializer.validated_data),
            ip=client_ip(request),
        )
        return ApiResponse.created(
            message="Enquiry recorded.", data=AdminEnquirySerializer(enquiry).data
        )


class AdminEnquiryDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Get an enquiry",
        responses={200: AdminEnquirySerializer},
    )
    def get(self, request, pk: int):
        enquiry = get_object_or_404(AdmissionEnquiry, pk=pk)
        return ApiResponse.success(data=AdminEnquirySerializer(enquiry).data)

    @extend_schema(
        tags=ADMIN_TAG,
        summary="Update status / notes, or link the admitted student",
        description="Linking a `student` marks the enquiry ACCEPTED.",
        request=EnquiryUpdateSerializer,
        responses={200: AdminEnquirySerializer},
    )
    def patch(self, request, pk: int):
        serializer = EnquiryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquiry = update_enquiry(
            actor=request.user,
            enquiry=get_object_or_404(AdmissionEnquiry, pk=pk),
            changes=serializer.validated_data,
            ip=client_ip(request),
        )
        return ApiResponse.success(
            message="Updated.", data=AdminEnquirySerializer(enquiry).data
        )
