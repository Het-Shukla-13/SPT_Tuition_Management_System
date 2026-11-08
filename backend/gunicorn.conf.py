"""
Gunicorn (production WSGI server) settings. Values can be tuned through
environment variables without rebuilding the image.

Worker model: a few processes x several threads ("gthread"). Threads suit
this app: most waiting is on PostgreSQL or Google Drive (file streaming), not
CPU. 2 workers x 4 threads = 8 requests at once, using at most 8 DB connections.
"""

import os

bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

# Kill a request stuck longer than this (PDF/photo uploads to Drive included).
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5

# Recycle workers now and then so a slow memory leak can never build up.
max_requests = 2000
max_requests_jitter = 200

# Only Caddy can reach this port (it isn't published), so trust its
# X-Forwarded-* headers. Django's own TRUSTED_PROXY_COUNT decides client IPs.
forwarded_allow_ips = "*"

# Django's RequestLoggingMiddleware already logs every request (without query
# strings); gunicorn's access log would duplicate it and leak query strings.
accesslog = None
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
