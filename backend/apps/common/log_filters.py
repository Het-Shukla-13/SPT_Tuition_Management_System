"""Logging filters."""

import logging

from apps.common.request_context import request_id_var


class RequestIDLogFilter(logging.Filter):
    """Attach the current request ID to every log record as `request_id`."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
