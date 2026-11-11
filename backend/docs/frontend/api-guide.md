# Frontend integration guide

The contract between the backend and the web app. The **exact** request and
response shapes of every endpoint are in Swagger (`/api/docs/`, development
only) or the OpenAPI file from `python manage.py spectacular --file schema.yaml`.
This guide covers what Swagger can't show: the rules that apply everywhere.

Error codes: [`error-codes.md`](error-codes.md) (generated from the code).

---

## 1. Basics

- Base path: `/api/v1/`. JSON in, JSON out (`Content-Type: application/json`),
  except file uploads (multipart) and file downloads.
- Areas by role:

  | Path | Who | What |
  |---|---|---|
  | `/auth/` | everyone | login, refresh, logout, own account and sessions |
  | `/academics/` | read: logged in · write: ADMIN | boards, standards, subjects, chapters, schools, academic years |
  | `/admin/` | ADMIN | users, students, fees, enquiries |
  | `/staff/` | ADMIN, TEACHER | tests, notes, assignments, marks, staff dashboard |
  | `/portal/students/{id}/` | PORTAL (parent/student) | that student's tests, notes, fees, overview |
  | `/public/enquiries/` | anyone | the "contact us" form |

- Formats:
  - **Money**: strings with 2 decimals, `"26000.00"`. Never parse to a float for
    arithmetic; display as is (or format with a decimal library).
  - **Date-times**: ISO 8601 with offset, India time: `2026-11-09T14:30:00+05:30`.
  - **Dates**: `YYYY-MM-DD`.
  - **IDs**: integers.
- Every response carries `X-Request-ID`. Show it in error dialogs ("quote this
  code when reporting a problem"): it finds the exact server log line.

## 2. The response envelope

Every JSON response, success or failure, from every endpoint:

```json
{
  "success": true,
  "message": "Human-readable, safe to show.",
  "data": {},
  "errors": null,
  "error_code": null,
  "meta": null
}
```

- `success: false` ⇒ `error_code` is set. Branch on `error_code`, never on
  `message` text. `errors` holds details: field errors for `VALIDATION_ERROR`
  (`{"field": ["message", ...]}`), `retry_after_seconds` for 429s, candidates
  for `POSSIBLE_DUPLICATE_STUDENT`.
- Also true for unknown URLs (404) and crashes (500): you never get HTML.

## 3. Lists: pagination, filters, search, ordering

```
GET /api/v1/admin/students/?page=2&page_size=50&standard=3&search=riya&ordering=-created_at
```

- `page_size` defaults to 20, maximum 100.
- `meta`: `{page, page_size, total_count, total_pages, has_next, has_previous}`.
- Unpaginated (small, returned whole, `meta: null`): `auth/sessions/`,
  `portal/students/`, `admin/fees/students/{id}/accounts/`.
- Filters are exact-match query params by id (`?board=1`) unless noted;
  `ordering` takes a field name, `-` prefix for descending.

| List | Filters | `search` matches | `ordering` |
|---|---|---|---|
| `admin/students/` | standard, board, school, status | name, admission no., guardian name/phone/email, linked login email/phone | first_name, last_name, admission_date, standard__level, created_at |
| `admin/users/` | role, is_active | email, phone | created_at, email, last_login |
| `admin/enquiries/` | status, standard, board | parent/student name, phone, email | created_at, status |
| `admin/fees/accounts/` | academic_year, academic_year__board, student__standard, student__school, student__status, student__admission_date__gte/__lte | student name, admission no., guardian phone | pending, total, paid, credit, last_payment_date, student__first_name, student__standard__level |
| `admin/fees/payments/` | entry_date__gte/__lte, method, amount__gte/__lte, recorded_by, account__academic_year | student name, admission no., receipt no., reference | entry_date, amount, created_at |
| `admin/fee-structures/` | academic_year, academic_year__board, standard, is_active | – | standard__level, total_fee |
| `staff/tests/` | board, standard, subject, semester, academic_year, chapters, school | title, description, subject, chapter names | created_at, updated_at, title, test_date |
| `staff/notes/` | board, standard, subject, semester, academic_year, chapters | title, description, subject, chapter names | created_at, updated_at, title |
| `staff/test-assignments/`, `staff/note-assignments/` | student, test_paper / note | – | – |
| `academics/*` | is_active (+ board/standard/subject for chapters, board/city for schools, board/is_current for academic years) | name (+code/city) | name / level / number |

## 4. Login and staying logged in

### Tokens
- **Access token**: in the JSON body of a login/refresh (`data.access`), valid
  15 minutes. Keep it **in memory only** (a variable / store), never in
  localStorage or sessionStorage. Send it as `Authorization: Bearer <access>`.
- **Refresh token**: set by the server as an **HttpOnly cookie**
  (`tms_refresh`, path `/api/v1/auth/`). The app never sees or stores it.
- All requests must include cookies: `fetch(url, { credentials: "include" })`
  (axios: `withCredentials: true`).

### Login flows (Phase 1.5)
Every login answer has `data.status`: `AUTHENTICATED` (logged in: `data.access`,
`data.user`, cookies set) or `OTP_REQUIRED` (show a 6-digit code box; the code was
emailed to `data.email`, masked). Requests must include cookies
(`credentials: "include"`): the trusted-device cookie decides whether a code is needed.

1. **Email + password**: `POST auth/login/` `{email, password}`.
   - `OTP_REQUIRED` → keep `data.login_ticket` in memory → `POST auth/login/verify/`
     `{login_ticket, code}`. "Resend code" → `POST auth/login/resend/` `{login_ticket}`.
   - `INVALID_CREDENTIALS` (any wrong combination) → show the message, which points to
     "Set or reset password". `LOGIN_LOCKED` / `OTP_COOLDOWN` → countdown from
     `errors.retry_after_seconds`. `LOGIN_TICKET_INVALID` → back to the password step.
2. **Set or reset password** (first visit of an invited user, or forgotten):
   `POST auth/password/reset/` `{email}` (same answer for unknown emails) →
   `POST auth/password/reset/confirm/` `{email, code, new_password}` → `AUTHENTICATED`.
   Weak password → `VALIDATION_ERROR` with `errors.new_password`; the code stays usable.
3. **Google**: get an ID token from Google Identity Services →
   `POST auth/google/` `{id_token}` → `AUTHENTICATED`, or `OTP_REQUIRED` (first link, or a
   new device) → `POST auth/google/verify/` `{id_token, code}`.
4. **Phone**: `POST auth/otp/request/` `{channel: "PHONE", identifier}` →
   `POST auth/otp/verify/` `{channel, identifier, code}`: a code every time. Unavailable
   until an SMS provider is set up (`OTP_DELIVERY_FAILED`): show email/Google only for now.

Logged in: `POST auth/password/change/` `{current_password, new_password}` (other devices
are logged out), `GET auth/devices/` + `DELETE auth/devices/{id}/` (trusted devices).

None of these auth calls should trigger the "401 → refresh" logic: a failed login is
a form error, not an expired session.

### App start / page reload
The in-memory access token is gone after a reload. On start, call
`POST auth/token/refresh/` with **no body** and header
`X-Requested-With: XMLHttpRequest`:
- `200` → `data.access`; then `GET auth/me/` for the user and continue.
- `401` → not logged in: show the login page.

### When a call returns 401
```
on 401 from any call except auth/token/refresh/:
    if no refresh is running: start one (POST auth/token/refresh/, header above)
    wait for it (ALL failing calls share this one refresh)
    success → retry the original call once with the new access token
    failure → clear state, go to login (remember the page to come back to)
```
- One shared refresh matters: refresh tokens rotate, and parallel refreshes
  from one tab would race. (Two **tabs** refreshing at once is fine: the server
  allows it within a 30-second window.)
- Never retry a 403: it means "not allowed", not "logged out".
- Refresh failure reasons: `SESSION_EXPIRED` (logged out elsewhere / too old),
  `NO_ACTIVE_ACCOUNT` (deactivated), `TOKEN_NOT_VALID`. Show a matching line
  on the login page.

### Logout
- `POST auth/logout/` (Bearer) ends this device's session and clears the cookie.
- `POST auth/logout-all/` ends every session of the account.
- Broadcast logout to other open tabs (`BroadcastChannel("auth")`) so they go
  to the login page too.

### Deployment requirement (cookie)
The cookie is `SameSite=Lax`: the web app and the API must be on the **same
site**: same hostname (Caddy serves both), or subdomains of one domain
(`app.example.in` + `api.example.in`). Different domains (e.g. `x.pages.dev` +
`y.duckdns.org`) don't work: Safari drops the cookie.

### Local development
Run the API on `http://localhost:8000` and the dev server on
`http://localhost:5173` (same site: ports don't matter). Set
`CORS_ALLOWED_ORIGINS=http://localhost:5173` in `backend/.env`. Development
also returns the refresh token in the body (`REFRESH_TOKEN_IN_BODY`), which
the app should ignore.

## 5. Portal (parents and students)

- `GET portal/students/` → the "Who's studying?" picker; `data` is the list of
  linked students, each with `is_selected` (the one last chosen on this device).
  With exactly one student, skip the picker.
- `POST portal/students/{id}/select/` remembers the choice **on this device**
  (stored on the session). Convenience only: every call still checks access.
- Everything else is per student: `portal/students/{id}/tests/`, `notes/`,
  `fees/`, `overview/`. A student not linked to this login answers `404`.

## 6. Files

- **Upload**: `multipart/form-data`, field names as in Swagger. PDFs only for
  tests/notes (checked: real PDF, size limit `MAX_UPLOAD_SIZE_MB` = 20 MB);
  photos JPEG/PNG/WebP up to 5 MB.
- **Download / view**: the endpoint streams the file with `Content-Type` and
  `Content-Disposition` (read the file name from it; it's exposed via CORS).
  Fetch with the Bearer header and open the blob; there are no public file URLs.
- Answer keys unlock after the test ends (`ANSWER_KEY_LOCKED` until then).

## 7. Writes that must not happen twice

- **Payments**: send an `Idempotency-Key` header (a new UUID per Save click).
  Retrying the same click (double-click, network retry) returns the same
  payment instead of recording it twice.
- Disable the submit button while a request is in flight.

## 8. Rate limits

Login-related endpoints are rate limited per IP and per identity. A `429`
carries `errors.retry_after_seconds` and a `Retry-After` header. For OTP
resend, show a countdown (`OTP_COOLDOWN`).
