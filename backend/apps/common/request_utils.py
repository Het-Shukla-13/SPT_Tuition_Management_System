"""Helpers for reading client metadata from a request."""

MAX_USER_AGENT_LENGTH = 512


def client_ip(request) -> str | None:
    # REMOTE_ADDR only. X-Forwarded-For is trivially spoofable and will be
    # trusted only once the production proxy setup is known (deployment phase).
    return request.META.get("REMOTE_ADDR")


def user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:MAX_USER_AGENT_LENGTH]
