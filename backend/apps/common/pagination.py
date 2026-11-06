"""Pagination that returns the standard envelope with page metadata."""

from rest_framework.pagination import PageNumberPagination

from apps.common.responses import ApiResponse


class StandardPagination(PageNumberPagination):
    """
    ?page=2&page_size=50

    `page_size` is capped so a client can never ask for thousands of rows
    in one response.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return ApiResponse.success(
            data=data,
            meta={
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "has_next": self.page.has_next(),
                "has_previous": self.page.has_previous(),
            },
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["success", "message", "data", "meta"],
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string", "example": "Success."},
                "data": schema,
                "errors": {"type": "object", "nullable": True, "example": None},
                "error_code": {"type": "string", "nullable": True, "example": None},
                "meta": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "example": 1},
                        "page_size": {"type": "integer", "example": 20},
                        "total_count": {"type": "integer", "example": 135},
                        "total_pages": {"type": "integer", "example": 7},
                        "has_next": {"type": "boolean", "example": True},
                        "has_previous": {"type": "boolean", "example": False},
                    },
                },
            },
        }
