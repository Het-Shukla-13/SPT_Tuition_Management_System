"""
ViewSet base that answers in the standard envelope (see responses.py).

DRF's ModelViewSet returns bare data for retrieve/create/update; lists are
already wrapped by StandardPagination. This wraps the rest, so every endpoint
built on it speaks the same shape. DELETE is not offered: records with history
are deactivated (is_active / soft delete), never removed through the API.
"""

from rest_framework import mixins, viewsets

from apps.common.responses import ApiResponse


class EnvelopeModelViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    http_method_names = ["get", "post", "patch", "head", "options"]

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return ApiResponse.success(data=response.data)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return ApiResponse.created(data=response.data)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return ApiResponse.success(message="Updated.", data=response.data)
