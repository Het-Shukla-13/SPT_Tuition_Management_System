# Production image for the Django backend.
# One image runs every backend role: the API (gunicorn), the one-off migrate
# step and the scheduler (`manage.py run_scheduler`) — like Labe1's API and
# worker containers sharing one image. Builds for x86 and ARM (Oracle Ampere).

# ── Stage 1: build the Python dependencies into a virtualenv ─────────────
FROM python:3.12-slim-trixie AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements/ /tmp/requirements/
# base.txt = what production needs; lock.txt pins the exact tested versions.
RUN pip install -r /tmp/requirements/base.txt -c /tmp/requirements/lock.txt

# ── Stage 2: the runtime image ────────────────────────────────────────────
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production

# PostgreSQL 18 client tools (pg_dump / pg_restore for backups) from the
# official PostgreSQL apt repository; Debian's own are older than the server,
# and pg_dump refuses to dump a newer server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Never run as root: a compromised app can't modify the system.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app . .

# Static files (admin CSS, Swagger assets) are collected at build time.
# These throwaway values only satisfy settings import; nothing connects anywhere.
RUN DJANGO_SECRET_KEY=build-only-not-a-real-secret-0123456789abcdefghijklmnopqrstuvwxyz \
    DJANGO_ALLOWED_HOSTS=build.invalid \
    DATABASE_URL=postgres://build:build@build.invalid:5432/build \
    EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend \
    python manage.py collectstatic --noinput \
    && mkdir -p /app/backups && chown app:app /app/backups

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "scripts/healthcheck.py"]

CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
