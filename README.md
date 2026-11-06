# SPT Tuition Management System

A tuition-institute management platform: OTP / Google sign-in, student
management, test-paper and notes archives with per-student assignment,
fee ledgers, and admin/student dashboards.

| Part | Stack | Status |
|---|---|---|
| `backend/` | Python 3.12, Django 5.2 LTS, DRF, PostgreSQL, SimpleJWT, drf-spectacular | In progress |
| `frontend/` | TBD | After the backend is complete |

---

## Backend: local setup (Windows / PowerShell)

### 1. Prerequisites
- Python 3.12 (`py -3.12 --version`)
- PostgreSQL 16+ with pgAdmin

### 2. Create the database
In pgAdmin → Query Tool (connected as `postgres`), or in `psql -U postgres`:

```sql
CREATE USER tms_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE tms_db OWNER tms_user;
-- lets the test runner create/drop its throwaway test_tms_db database
ALTER USER tms_user CREATEDB;
```

### 3. Virtual environment and dependencies
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements/dev.txt
```

### 4. Environment variables
```powershell
Copy-Item .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```
Open `.env`, paste the generated key into `DJANGO_SECRET_KEY`, and set the
password in `DATABASE_URL`.

### 5. Initialise and run
```powershell
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser        # the first ADMIN account
python manage.py runserver
```

| URL | What |
|---|---|
| http://127.0.0.1:8000/api/docs/ | Swagger UI |
| http://127.0.0.1:8000/api/v1/health/ | Liveness check |
| http://127.0.0.1:8000/api/v1/health/ready/ | Readiness check (DB + cache) |
| http://127.0.0.1:8000/admin/ | Django admin |

### 6. Quality checks
```powershell
pytest                       # tests (uses a separate test_tms_db database)
pytest --cov                 # with coverage
ruff check . ; ruff format . # lint + format
pre-commit install           # (run from repo root, once) auto-check on commit
```

---

## Backend layout

```
backend/
├── config/
│   ├── settings/        base · development · production · test
│   ├── urls.py          /api/v1/…, /api/docs/, /admin/
│   └── wsgi.py / asgi.py
├── apps/
│   ├── common/          base models, response envelope, exceptions,
│   │                    pagination, request-ID middleware, health checks
│   └── accounts/        User model, OTP sign-up/login, JWT refresh/logout
│       └── services/    otp, otp_delivery, otp_rate_limit, sms, tokens
├── FAQ.md               business rules behind the API (keep in sync!)
├── requirements/        base · dev · prod
├── conftest.py          shared pytest fixtures
└── pyproject.toml       ruff + pytest config
```

### Conventions
- **Response envelope**: every endpoint returns
  `{success, message, data, errors, error_code, meta}`.
- **Secure by default**: every endpoint requires a JWT unless it explicitly opts out.
- **Integer primary keys** (Django default `BigAutoField`); access is enforced by permission checks.
- **Base models** (as in Labe1): `GlobalTimeStampedModel` (timestamps) and
  `AbstractTimeStampedModel` (timestamps + soft delete with `is_deleted` / `deleted_at`).
- **Business logic lives in `services.py`**, not in views or serializers.
- **Money uses `DecimalField`**, never floats.
- **Nothing with history is hard-deleted**: soft-delete or deactivate instead.
