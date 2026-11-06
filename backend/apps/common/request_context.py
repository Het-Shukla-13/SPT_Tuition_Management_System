"""
Per-request context shared between middleware and logging.

A ContextVar is safe for both threaded (WSGI) and async (ASGI) servers:
each request sees only its own value. Kept free of Django imports so the
logging configuration can import it at startup.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
