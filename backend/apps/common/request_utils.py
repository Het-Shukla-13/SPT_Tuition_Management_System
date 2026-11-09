"""Helpers for reading client metadata from a request."""

from django.conf import settings

MAX_USER_AGENT_LENGTH = 512


def client_ip(request) -> str | None:
    """
    The caller's IP address.

    With TRUSTED_PROXY_COUNT = N > 0, take the N-th address from the RIGHT of
    X-Forwarded-For: each trusted proxy appends the address it received the
    connection from, so that entry was written by our own proxy and can't be
    forged. Anything further left came from the client. Same rule as DRF's
    NUM_PROXIES, so audit logs and rate limits agree on who the caller is.
    """
    count = settings.TRUSTED_PROXY_COUNT
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if count > 0 and forwarded:
        addresses = [part.strip() for part in forwarded.split(",") if part.strip()]
        if addresses:
            return addresses[-min(count, len(addresses))]
    return request.META.get("REMOTE_ADDR")


def user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:MAX_USER_AGENT_LENGTH]
