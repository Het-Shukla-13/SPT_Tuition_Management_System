"""
Container health check: is the API answering and can it reach the database?

Exit 0 = healthy. Used by the Dockerfile HEALTHCHECK, so Docker restarts the
container (and `docker compose ps` shows "unhealthy") if the app hangs.
Standard library only, so it works even if the app's imports are broken.
"""

import os
import sys
import urllib.request

host = (os.environ.get("DJANGO_ALLOWED_HOSTS") or "localhost").split(",")[0].strip()
request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/health/ready/",
    headers={"Host": host, "X-Forwarded-Proto": "https"},
)
try:
    with urllib.request.urlopen(request, timeout=4) as response:  # noqa: S310
        sys.exit(0 if response.status == 200 else 1)
except Exception as exc:  # noqa: BLE001
    print(f"unhealthy: {exc}", file=sys.stderr)
    sys.exit(1)
