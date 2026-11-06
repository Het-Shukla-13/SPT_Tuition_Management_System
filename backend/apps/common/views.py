"""Health-check endpoints used by the hosting platform and monitoring."""

import logging
import uuid

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.common.responses import ApiResponse

logger = logging.getLogger(__name__)


class LivenessView(APIView):
    """Is the process up? No dependencies checked — always cheap."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        tags=["Health"],
        summary="Liveness check",
        responses={200: OpenApiResponse(description="Service process is running.")},
    )
    def get(self, request):
        return ApiResponse.success(data={"status": "ok"}, message="Service is running.")


class ReadinessView(APIView):
    """Can the service handle traffic? Verifies the database and cache."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(
        tags=["Health"],
        summary="Readiness check (database + cache)",
        responses={
            200: OpenApiResponse(description="All dependencies are reachable."),
            503: OpenApiResponse(description="A dependency is unavailable."),
        },
    )
    def get(self, request):
        checks = {"database": self._check_database(), "cache": self._check_cache()}
        if all(result == "ok" for result in checks.values()):
            return ApiResponse.success(data=checks, message="Service is ready.")
        # Report which dependency failed, never why (no internal details leak).
        return ApiResponse.error(
            message="Service is not ready.",
            error_code="SERVICE_UNAVAILABLE",
            errors=checks,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @staticmethod
    def _check_database() -> str:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            logger.exception("Readiness: database check failed")
            return "unavailable"
        return "ok"

    @staticmethod
    def _check_cache() -> str:
        key = f"health:{uuid.uuid4().hex}"
        try:
            cache.set(key, "1", timeout=5)
            ok = cache.get(key) == "1"
            cache.delete(key)
        except Exception:
            logger.exception("Readiness: cache check failed")
            return "unavailable"
        return "ok" if ok else "unavailable"
