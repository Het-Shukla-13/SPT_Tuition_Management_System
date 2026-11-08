# Backend FAQ: business logic behind the API

This documents the behaviour you would otherwise have to read the code to learn:
silent defaults, gating rules, status semantics and edge cases. **Update it in the
same change whenever you add or change such logic** (a stale entry is worse than none).

All endpoints are under `/api/v1/`. Every response uses the envelope
`{success, message, data, errors, error_code, meta}`.

---

## 1. Authentication (`/api/v1/auth/`)

### Can anyone sign up?
**No. The platform is invite-only** (one institute). Logins are created only by the owner/admins
(`POST /api/v1/admin/users/`, section 3), with the person's name already filled in. There is no
public registration, and Google sign-in never creates accounts.

### How does an invited person log in?
Passwordless, with a one-time code (OTP) by email or SMS:

1. `POST otp/request/` `{channel: EMAIL|PHONE, identifier}` (`purpose` is optional; only `LOGIN` exists)
2. `POST otp/verify/` `{channel, identifier, code}` → `{access, refresh, user}`

The first successful login sets `users.activated_at` ("invite accepted") and marks that email/phone
verified. Logic: `apps/accounts/services/otp.py`.

### Does `otp/request/` tell me whether an account exists?
No, by design (spec §10.1, account enumeration). The response is always the same
`200 "If the details are valid, a verification code has been sent."`:

| Account | What actually happens |
|---|---|
| Exists and active | Code sent |
| Doesn't exist / deactivated / soft-deleted | Nothing sent |

Cooldowns and limits also apply identically in every row, so they reveal nothing either.

### Can a code be used for something else?
No. A code only works for the `purpose` (and `channel` + `identifier`, and bound context) it was
issued for: login codes can't link Google or change contact details, and vice versa.

### What are the OTP rules?
| Rule | Default | Setting |
|---|---|---|
| Length | 6 digits | `OTP_LENGTH` |
| Validity | 5 minutes | `OTP_TTL_SECONDS` |
| Wrong guesses before lock | 5 (then request a new code) | `OTP_MAX_ATTEMPTS` |
| Resend cooldown per identifier | 60 s → `429 OTP_COOLDOWN` + `Retry-After` | `OTP_RESEND_COOLDOWN_SECONDS` |
| Requests per identifier per hour | 5 → `429 OTP_REQUEST_LIMIT_REACHED` | `OTP_MAX_REQUESTS_PER_HOUR` |
| Requests per IP | 20/hour → `429 THROTTLED` | `THROTTLE_RATE_OTP_REQUEST` |
| Verifications per IP | 60/hour → `429 THROTTLED` | `THROTTLE_RATE_OTP_VERIFY` |

- Codes are stored **hashed** (`make_password`), never in plain text (`OTPChallenge.code_hash`).
- Codes are **one-time**: a verified code can't be used again.
- **Latest code wins**: requesting a new code invalidates the previous one. The DB
  enforces at most one active code per (channel, identifier, purpose).
- Verification locks the OTP row (`select_for_update`), so parallel guesses can't
  exceed the attempt limit or consume a code twice.

### What error codes can `otp/verify/` return?
| Code | HTTP | Meaning |
|---|---|---|
| `OTP_INVALID` | 400 | Wrong code, or no active code (same message for both) |
| `OTP_EXPIRED` | 400 | Code expired; request a new one |
| `OTP_ATTEMPTS_EXCEEDED` | 429 | 5th wrong guess; this code is dead |
| `ACCOUNT_DISABLED` | 403 | LOGIN, but the account was deactivated after the code was sent |

### What happens if the email/SMS can't be sent?
`503 OTP_DELIVERY_FAILED`, and the unsent code is invalidated. We never claim
success for a code nobody received.

### What if the cache (rate-limit store) is down?
**Fail closed**: OTP requests return `503 OTP_TEMPORARILY_UNAVAILABLE` and the OTP
endpoints' IP throttle returns `503 THROTTLE_UNAVAILABLE` (`Retry-After: 30`). Losing the
limits must not mean unlimited OTP emails or guesses. The global anon/user throttles
**fail open** (they only smooth load). See `apps/common/throttling.py`.

### How does "Continue with Google" work?
Logic: `apps/accounts/services/google.py`. The frontend gets a Google **ID token** from Google
and sends it to us; we verify it with Google's official library (signature, expiry, issuer, and
that it was issued for **our** client ID: `GOOGLE_OAUTH_CLIENT_ID`).

1. `POST google/` `{id_token}`
   - Google account already linked → `status: AUTHENTICATED` + `access`, `refresh`, `user`.
   - Not linked yet → `status: OTP_REQUIRED`, `email` (masked). A 6-digit code is emailed
     to the Google account's address.
2. `POST google/verify/` `{id_token, code}` (same Google token) → links the Google account to the
   invited account that owns that email, then logs in. **Google never creates accounts**: for an
email with no login, step 1 answers `OTP_REQUIRED` as usual but sends nothing.

Every later Google sign-in is one click. Each one starts its own session, like any login.

### Why an email code the first time, if Google already verified the email?
A Google account can carry an email address its creator doesn't own (non-Gmail addresses).
Matching emails alone could let someone take over a student's account. Only the inbox owner can
read the code, so only they can link. The code is **bound to that Google account** (`sub`):
a code sent for one Google account can't complete the link for another.

### What can go wrong with Google sign-in?
| Code | HTTP | Meaning |
|---|---|---|
| `GOOGLE_TOKEN_INVALID` | 401 | Forged/expired token, issued for another app, wrong issuer, or no email |
| `GOOGLE_EMAIL_NOT_VERIFIED` | 400 | Google says the email isn't verified |
| `ACCOUNT_DISABLED` | 403 | The linked account is deactivated or deleted |
| `GOOGLE_ACCOUNT_CONFLICT` | 409 | The email's account is already linked to a *different* Google account |
| `GOOGLE_UNAVAILABLE` | 503 | Couldn't reach Google; use email/phone OTP instead |
| `GOOGLE_NOT_CONFIGURED` | 503 | `GOOGLE_OAUTH_CLIENT_ID` isn't set on the server |
Plus all the usual OTP errors/limits on the code (cooldown, attempts, expiry).

If the email belongs to a disabled/deleted account, step 1 still answers `OTP_REQUIRED` but sends
nothing, so the response doesn't reveal the account's state.

### Can I request a `GOOGLE_LINK` code myself, or use a login code to link Google?
No. `GOOGLE_LINK` codes are only issued by `google/`; `otp/request/` accepts only
`LOGIN`, and codes only work for the purpose they were issued for.

### How do I unlink Google?
`POST google/unlink/` (authenticated). Email OTP login keeps working; current sessions stay; the
next Google sign-in needs an email code again. `GET me/` shows `google_linked`.
Linking and unlinking are recorded in the audit log.

**Not stored:** the raw Google token (unlike Labe1). Only Google's account id (`users.google_id`).

**Manual testing:** `backend/tools/google_signin_tester.html` (instructions inside).

### How are phone numbers and emails normalised?
Before storage, lookup and rate-limiting (`apps/accounts/identifiers.py`):
- Email: trimmed + lowercased.
- Phone: spaces/dashes/brackets removed, `00` → `+`, a bare 10-digit number gets
  `DEFAULT_PHONE_COUNTRY_CODE` (`+91`), result must be E.164 (`+919876543210`).

### Who decides a login's role?
Whoever creates it (section 3): admins create `TEACHER` and `PORTAL` logins; only the owner creates
`ADMIN`s. A `role` sent to the login endpoints is ignored.

### How do tokens and sessions work?
Every successful OTP verification starts a **session** (`UserSession`, one per login/device).
Both tokens carry the session's id as the `sid` claim. Logic: `apps/accounts/services/tokens.py`,
`apps/accounts/services/sessions.py`, `apps/accounts/authentication.py`.

- Access token: 15 min (`JWT_ACCESS_TOKEN_LIFETIME_MINUTES`). Send `Authorization: Bearer <access>`.
- Refresh token: 7 days (`JWT_REFRESH_TOKEN_LIFETIME_DAYS`), sliding: each refresh extends it.
- Hard cap: a session can't be refreshed beyond **30 days** after login (`SESSION_MAX_LIFETIME_DAYS`)
  → `401 SESSION_EXPIRED`; log in again.
- **Every authenticated request checks the session in the database.** A revoked session's
  access token is rejected immediately (`401 TOKEN_NOT_VALID`), not after it expires.
- A token without a `sid`, with a different issuer/audience (`spt-tms-api` / `spt-tms`),
  or a bad signature → `401`.
- Tokens carry a `role` claim **for the frontend only**. The backend always reads the role
  from the database (a forged `role: ADMIN` claim changes nothing).

### What exactly happens on `POST token/refresh/`?
`{refresh}` → returns `{access, refresh}`. The refresh token **rotates**: store the new one,
the old one stops working.

| Situation | Result |
|---|---|
| Normal refresh | `200`, new pair; session `last_active_at` / `expires_at` updated |
| Same old token sent again **within 30 s** (`REFRESH_ROTATION_GRACE_SECONDS`), e.g. two tabs | `200` with the **same** new pair (no false logout) |
| Same old token sent again **after 30 s** | `401` and the **whole session is revoked** (`REFRESH_REUSE`): someone else may hold a copy |
| Session logged out / revoked / user disabled or deleted | `401` |
| Garbage, expired, or an access token instead | `401 TOKEN_NOT_VALID` |

Simultaneous refreshes are serialised by a row lock on the session.

### What does logout do?
- `POST logout/` (authenticated): ends **this device's** session. Its access and refresh tokens
  die at once; other devices stay logged in. Optional body `{refresh}`; if sent it must belong
  to you, otherwise `400 INVALID_REFRESH_TOKEN`.
- `POST logout-all/`: ends **every** session of the account, including this one.
  Returns `{sessions_ended: n}`.

### How do I see and end my sessions (devices)?
- `GET sessions/`: your active sessions: `id`, `created_at`, `last_active_at`, `expires_at`,
  `ip_address`, `user_agent`, `is_current`.
- `DELETE sessions/{id}/`: end one of them (e.g. a lost phone). Someone else's session id →
  `404` (indistinguishable from "doesn't exist").

Revoked sessions keep their row with `revoked_at` + `revoked_reason`
(`LOGOUT`, `LOGOUT_ALL`, `REVOKED_BY_USER`, `REFRESH_REUSE`, `LIFETIME_EXCEEDED`) for auditing.

### What happens to a soft-deleted or deactivated user's tokens?
Both access and refresh tokens stop working immediately (`401`): authentication looks
the user up through the default manager, which hides soft-deleted users, and checks `is_active`.

---

## 2. Roles and permissions

### What roles exist?
| Role | Who | How the account is created |
|---|---|---|
| `TEACHER` | Teaching staff: tests, notes, assignments, grading. No invites, no fees | Admin |
| `PORTAL` | Parents / students who view the student(s) linked to their login | Admin |
| `ADMIN` | Institute staff | Owner: `POST admin/users/` or `POST admin/users/{id}/role/` |
| `ADMIN` + `is_superuser` ("owner") | The institute owner(s) | Only `python manage.py createsuperuser` |

Permission classes live in `apps/common/permissions.py`: `IsAdmin`, `IsTeacher`,
`IsStaff` (admin or teacher), `IsPortalUser`, `IsSuperUser` (owner), and object-level `IsOwnerOrAdmin`.

### Where does the backend get a user's role from?
Always from the database row loaded for the request, **never** from the JWT `role` claim.
An inactive user matches no role. Denials are logged (user, role, method, path, object id).
Anonymous → `401`; authenticated but not allowed → `403 PERMISSION_DENIED`.

### How does "students can only see their own records" work?
`IsOwnerOrAdmin` (object-level): admins pass; anyone else must own the object, found via
the view's `owner_field` (default `user`, dotted paths like `student.user` allowed).
Changing an ID in the URL to someone else's record → `403`.

## 3. Admin user management (`/api/v1/admin/users/`)

All endpoints need role `ADMIN`. Logic: `apps/accounts/services/users.py`.

| Endpoint | Who | Notes |
|---|---|---|
| `POST /` | ADMIN | **Create a login (invite)**: `first_name`, `last_name`, `role`, `email` and/or `phone`. Invite goes by email and/or SMS (`invite_sent` per channel; a failed send keeps the login). Only the owner may create `ADMIN`. `409 CONTACT_IN_USE` if taken |
| `POST /{id}/resend-invite/` | ADMIN | Before their first login only (`INVITE_ALREADY_ACCEPTED` after) |
| `PATCH /{id}/` | ADMIN | Fix a name (`OWNER_REQUIRED` for another admin) |
| `GET /` | ADMIN | Paginated. `?search=` (email/phone), `?role=`, `?is_active=`, `?ordering=created_at\|email\|last_login` (prefix `-`) |
| `GET /{id}/` | ADMIN | Soft-deleted users → `404` |
| `POST /{id}/deactivate/` | ADMIN | Can't log in any more; **all sessions end immediately**. Records untouched. Idempotent |
| `POST /{id}/activate/` | ADMIN | Idempotent |
| `POST /{id}/role/` `{role}` | **Owner only** | Grants/revokes ADMIN; the user's sessions end so the new role applies everywhere |

### What is refused?
| Rule | Error |
|---|---|
| Changing your own role or deactivating yourself | `403 CANNOT_MODIFY_SELF` |
| A non-owner admin deactivating/activating another ADMIN | `403 OWNER_REQUIRED` |
| A non-owner changing anyone's role | `403 PERMISSION_DENIED` |
| Demoting or deactivating the **last active ADMIN** | `409 LAST_ADMIN` |

Concurrent demotions are serialised with row locks, so two at once can't remove the last admin.

### Is any of this recorded?
Yes, in `audit_logs` (`apps/audit`), in the same transaction as the change: action
(`USER_ROLE_CHANGED`, `USER_DEACTIVATED`, `USER_ACTIVATED`), actor, target, `changes`
(e.g. `{"role": ["PORTAL", "ADMIN"]}`), IP and request ID. Read-only in Django admin.

## 4. Account settings: email & phone (`/api/v1/auth/me/contact/`)

Logic: `apps/accounts/services/contact.py`.

### How do I add or change my email/phone?
1. `POST me/contact/` `{channel, identifier}` (the **new** value). A `CONTACT_CHANGE` code is sent
   to the new email/phone. Response: `sent_to` (masked), expiry, resend wait.
2. `POST me/contact/verify/` `{channel, identifier, code}` saves it **verified**.

- The code is bound to **you** (`context.user_id`): another user can't complete it.
- The **old** email/phone gets a "your … was changed" notice (sent after commit, best effort).
- Login codes / Google codes can't be used here; `CONTACT_CHANGE` codes aren't requestable via `otp/request/`.
- Existing sessions stay logged in. A Google link is unaffected (it's tied to the Google account id).
- The old email/phone stops working for login immediately (no account has it any more).
- Limits: the usual OTP cooldown/hourly cap on the new identifier, plus `10/hour` per user
  (`THROTTLE_RATE_CONTACT_CHANGE`).

| Error | When |
|---|---|
| `CONTACT_UNCHANGED` (400) | It's already your value |
| `CONTACT_IN_USE` (409) | Another account (incl. soft-deleted) has it, checked at request **and** at verify |
| `OTP_*` | Usual code errors |

> Note: `CONTACT_IN_USE` tells a logged-in user that an address is registered. Accepted on purpose
> (clear UX for the person adding their own number); bounded by the per-user throttle.

### How do I remove my email or phone?
`DELETE me/contact/email/` or `DELETE me/contact/phone/`. Only if the other one remains
(`LAST_CONTACT_METHOD` otherwise; the DB also enforces "email or phone required"). The removed
address is notified.

### A student lost access to their email/phone. What now? (spec §2.5)
An admin calls `POST /api/v1/admin/users/{id}/contact/` `{channel, identifier}` (or `identifier: null`
to remove). The value is stored **unverified** and becomes verified on the user's first OTP login
with it. The old address is notified. Not for your own account (`CANNOT_MODIFY_SELF`); only the
owner may edit another admin (`OWNER_REQUIRED`). Audited with `by_admin: true`.

## 5. Academic reference data (`/api/v1/academics/`)

`boards/`, `standards/`, `subjects/`, `chapters/`, `schools/`, `academic-years/`. Logic: `apps/academics`.

- **Seeded:** boards CBSE / GSEB / ICSE; standards 1st-10th; subjects English, Mathematics, Science,
  Social Studies, Gujarati, Hindi (English medium only); academic year 2026-27 (1 Apr 2026 - 31 Mar 2027)
  as current. Admins can change all of it.
- **Read:** any logged-in user, **active items only**. Admins also see inactive ones (`?is_active=false`).
- **Write:** admins only (`POST`, `PATCH`). **No DELETE (405):** deactivate with `PATCH {"is_active": false}`.
  Rows referenced by other records are protected from deletion at the database level too.
- **Uniqueness (ignoring case):** board `code`; subject `name` and `code`; school `name` + `city`;
  standard `level`; chapter `number` per board + standard + subject.
- **Chapters** belong to a board + standard + subject (CBSE 10th Maths ch. 1 ≠ GSEB 10th Maths ch. 1).
  Filter: `?board=&standard=&subject=`.
- **Academic year:** exactly one can be current. Creating/updating one with `is_current: true`
  switches the previous one off in the same transaction. `end_date` must be after `start_date`.

## 6. Students (`/api/v1/admin/students/`, `/api/v1/portal/students/`)

Logic: `apps/students/services.py`. Design: `docs/plans/phase-2-core-data.md`.

### What is a "student" vs a "login"?
- **StudentProfile** = the child (name, board, standard, school, guardian contact on file…). Not a login.
- **Login** (`User`, role `PORTAL`) = whoever signs in: usually a parent, sometimes the student.
- **StudentAccess** links them: one login can see several students (siblings), one student can be
  seen by several logins (mom, dad, the kid's own phone). Everyone linked sees the same student data.

### How is a student admitted? (`POST /admin/students/`, admin only)
One transaction creates: the profile (auto `admission_number` `SPT-<year>-0001`, never repeated),
current subjects, the first academic-history row (`ADMISSION`, in the current academic year), and
access for `link_user_ids` (existing logins, e.g. a sibling's parent) and `new_logins` (created as
`PORTAL` and invited by SMS/email **after** the transaction commits).
- Required: first & last name, board, standard, school, at least one subject (no repeats).
- A student may have no login yet.
- Fails as a whole (nothing created, no invite sent) on: `NO_CURRENT_ACADEMIC_YEAR`,
  `INACTIVE_REFERENCE` (deactivated board/standard/school/subject), `NOT_A_PORTAL_LOGIN`
  (linking an admin/teacher), `CONTACT_IN_USE` (new login's phone/email taken).
- **Possible duplicate** (same name AND same/unknown birth date or same guardian phone) →
  `409 POSSIBLE_DUPLICATE_STUDENT` listing candidates; resend with `confirm_duplicate: true`.
  Same name with a different birth date is fine.
- Guardian phone is normalised like login phones (`+91…`).

### What else can admins do?
| Endpoint | Notes |
|---|---|
| `GET /` | Search (name, admission no., guardian phone/email, linked login's phone/email), filter `standard`/`board`/`school`/`status`, sort, paginate |
| `GET /{id}/` | Profile + current subjects + linked logins (with `invite_accepted`) |
| `PATCH /{id}/` | Personal details only |
| `POST /{id}/academic/` `{board?, standard?, school?, reason}` | Closes the current history row, opens a new one. `NOTHING_CHANGED` if identical |
| `GET /{id}/history/` | Academic history, newest first |
| `POST /{id}/status/` `{ACTIVE\|ON_HOLD\|LEFT}` | `LEFT` sets `left_on`; nothing is deleted |
| `PUT /{id}/subjects/` | Replace current subjects; dropped ones get `ended_on` (kept) |
| `GET/POST /{id}/access/` | List logins / grant: `{user_id}` or `{new_login}` (created + invited). `ACCESS_ALREADY_GRANTED` |
| `DELETE /{id}/access/{user_id}/` | Unlink (row kept with `revoked_at`); devices that had it selected forget it. The login stays |

Everything is audited. Reference data in use can't be deleted (`PROTECT`).

### What does a parent/student login see? (`/portal/students/`, `PORTAL` only)
- `GET /`: their linked students (the "Who's studying?" picker), with `is_selected` for this device.
- `GET /{id}/`: one linked student. **Not linked → 404** (changing the id reveals nothing).
- `POST /{id}/select/`: remember this student on this device (stored on the session, like Labe1's
  active group). Two devices can have different students selected. It's never a permission.
- A `LEFT` student still appears, with its status. A login with no links sees an empty list.
- Admins/teachers get `403` on portal endpoints; portal logins get `403` on admin endpoints.

## 7. Admission enquiries

- **Public** `POST /api/v1/public/enquiries/` (no login): `parent_name`, `phone`, `student_name`,
  optional `email`, `standard`, `board`, `message`. Stores a request and emails active admins.
  **Never creates a login or a student.** Throttled `5/hour` per IP (fail closed). A filled
  `website` field (hidden honeypot) gets a fake success and nothing is stored.
- **Admin** `GET /api/v1/admin/enquiries/` (filter `status`, search name/phone/email),
  `GET/PATCH /{id}/` (`status` NEW/CONTACTED/ACCEPTED/REJECTED, `notes`, `student`). Linking a
  `student` (after admitting them through the admission form) marks it ACCEPTED. Audited.

## 8. Tests & notes (`/api/v1/staff/...`, `/api/v1/portal/students/{id}/...`)

Logic: `apps/learning/services.py`. Design: `docs/plans/phase-3-tests-notes.md`.

### Who can do what?
- **Admins and teachers** (`IsStaff`): upload, edit, replace PDFs, archive, assign, revoke, grade.
- **Portal logins** (parents/students): only assignments of their **linked, ACTIVE** student.
  Another student's id or assignment id → `404`.

### How are files protected?
- **No public file URLs.** PDFs are only served by `.../download/` endpoints after permission checks
  (`Cache-Control: private, no-store`); every portal download is audited (`FILE_ACCESSED`).
- Uploads: **PDF only, checked by content** (`%PDF-` signature + parsed by pypdf), so renamed
  executables and corrupt PDFs are rejected (`INVALID_PDF`); max `MAX_UPLOAD_SIZE_MB` (`FILE_TOO_LARGE`).
- Stored under random names; the DB keeps only the storage path. Local disk now, **Google Drive in Phase 6**.
- The exact same PDF already uploaded elsewhere → `409 DUPLICATE_DOCUMENT` (resend `confirm_duplicate`).

### Staff endpoints
| Endpoint | Notes |
|---|---|
| `GET/POST /staff/tests/` | Archive list (search title/subject/chapter; filter board/standard/subject/semester/academic_year/chapters/school; sort; archived hidden unless `?is_archived=true`). POST = multipart upload: details + `file` (+ optional `answer_key`) |
| `GET/PATCH /staff/tests/{id}/` | Details. Chapters must match the paper's board + standard + subject |
| `POST /staff/tests/{id}/paper/` · `POST/DELETE .../answer-key/` | Replace PDF → **new version, old kept**; students always get the latest |
| `GET .../versions/` · `GET .../download/?kind=PAPER\|ANSWER_KEY&version=&inline=` | |
| `POST .../archive/` `{archived}` | Archived = hidden + can't be newly assigned; existing assignments stay |
| `POST .../assign/` `{student_ids, test_starts_at?, duration_minutes?, remarks}` | Bulk; returns `assigned` + `failed` (`NOT_FOUND`, `STUDENT_NOT_ACTIVE`, `ALREADY_ASSIGNED`) |
| Same for `/staff/notes/` (replace: `.../file/`) | No answer key / marks for notes |
| `GET /staff/test-assignments/` `?student=&test_paper=&status=active\|revoked\|all` | Also `/staff/note-assignments/` |
| `PATCH /staff/test-assignments/{id}/` | Change test time / duration / remarks |
| `POST /staff/test-assignments/{id}/grade/` `{marks_obtained, grade_remarks}` | 0 ≤ marks ≤ `max_marks` (`MARKS_OUT_OF_RANGE`) |
| `POST /staff/{test,note}-assignments/revoke/` `{assignment_ids}` | Bulk; rows kept (history). Revoke + reassign keeps both |

### When can a student see the answer key?
**Automatically once the test is over**: after `test_starts_at + duration` (the assignment's duration,
else the paper's). No test time set → never. Before that → `403 ANSWER_KEY_LOCKED`; no key uploaded →
`404 ANSWER_KEY_UNAVAILABLE`. Staff can reschedule the test time.

### Portal endpoints
`GET tests/` (assigned tests with dates, remarks, marks, `answer_key_available`), `GET tests/{id}/`,
`GET tests/{id}/download/?kind=PAPER|ANSWER_KEY`, `GET notes/?search=&subject=&chapter=`,
`GET notes/{id}/download/`. A student who is `ON_HOLD`/`LEFT` sees no tests/notes.

## 9. Fees, academic years per board, year-end rollover

Logic: `apps/fees/services.py`, `apps/fees/rollover.py`. Design: `docs/plans/phase-4-fees.md`.
**Admins only**; teachers and portal logins get `403` on fee admin endpoints.

### Academic years
Each **board has its own academic years** (dates typed in by the admin every year) and **its own current
year**. Student history, tests/notes and fee accounts use the student's board's year.

### How are fees stored?
- `FeeStructure`: standard fee per standard in a board's year. **Only a suggestion** for new admissions;
  editing it never changes existing students.
- `StudentFeeAccount`: one per student per academic year (created at admission with `agreed_fee`, default =
  fee structure, else `FEE_REQUIRED`; optional `opening_balance` + reason for dues from before the app).
- `LedgerEntry`: **append-only** money records: CHARGE, ADJUSTMENT (+/-), PAYMENT, REVERSAL, REFUND,
  CARRY_OUT. **Never edited or deleted.** Totals are always computed from entries.

### What do total / paid / pending / status mean?
`total = opening_balance + agreed fee + adjustments`; `paid = payments - reversals - refunds`;
`due = total + carried - paid`. `pending = due if > 0`, `credit = -due if < 0`.
Status: `PAID`, `PARTIAL`, `PENDING`, `CREDIT` (overpaid), `CARRIED_FORWARD` (moved to next year).
`is_overdue` = dues after the year's end date; `is_ending_soon` = dues within 30 days of it.

### How are mistakes and duplicates handled? (spec 8.6)
- **Double "Save":** send an `Idempotency-Key` header with each payment; the same key again returns the
  original payment (200) instead of recording it twice. The same key on another account → `409 IDEMPOTENCY_CONFLICT`.
- **Wrong payment:** `POST /admin/fees/entries/{id}/reverse/` `{reason}`, then record the right one. Once per payment
  (`ALREADY_REVERSED`), payments only (`NOT_A_PAYMENT`).
- **Fee changed:** `POST .../agreed-fee/` `{agreed_fee, reason}` → recorded as an adjustment of the difference.
- **Concession / extra charge:** `POST .../adjustments/` `{amount (+/-), reason}`.
- **Refund:** `POST .../refunds/`, at most what was actually paid (`REFUND_TOO_LARGE`).
- **Overpayment** becomes credit and is carried into next year at rollover.
- Every write locks the account row (two admins at once can't corrupt totals) and is audited.

### Validation
Amount > 0 (≤ 2 decimals) → `INVALID_AMOUNT`; date not in the future → `FUTURE_DATE`; method CASH/UPI/
BANK_TRANSFER/CHEQUE/OTHER (OTHER needs remarks → `NOTE_REQUIRED`); reasons required for adjustments,
reversals, refunds; agreed fee ≥ 0; one account per student per year.

### Endpoints
| Endpoint | Notes |
|---|---|
| `/admin/fee-structures/` | CRUD (no delete); filter year/board/standard |
| `GET /admin/fees/accounts/` | Fees table. `?status=PAID\|PARTIAL\|PENDING\|CREDIT\|CARRIED_FORWARD\|OVERDUE\|ENDING_SOON`, `pending_min/max`, `paid_min/max`, `total_min/max`, `academic_year`, `academic_year__board`, `student__standard`, `student__school`, `student__status`, `student__admission_date__gte/lte`; search name/admission no./guardian phone; `ordering=-pending\|total\|paid\|credit\|last_payment_date\|student__first_name\|student__standard__level` |
| `GET /admin/fees/accounts/{id}/` | Totals + full ledger |
| `GET /admin/fees/students/{student_id}/accounts/` | Every year of one student |
| `POST .../payments/` · `.../adjustments/` · `.../agreed-fee/` · `.../refunds/` | See above |
| `GET /admin/fees/payments/` | All payments: `entry_date__gte/lte`, `method`, `amount__gte/lte`, `recorded_by`, `reversed=true\|false`, search |
| `GET /admin/fees/payments/{id}/receipt/` | PDF receipt (`RCPT-<year>-NNNNN`; shows "REVERSED" if reversed) |
| `GET /portal/students/{id}/fees/` · `.../fees/receipts/{entry_id}/` | Parents/students: read-only, every year; remarks only if `visible_to_student` |

### Year-end rollover (per board)
1. Admin creates the board's next academic year (dates for that year) and its fee structures.
2. `POST /admin/rollover/preview/` `{board, to_year}` → each ACTIVE student with `suggested_action`
   (`PROMOTE` to the next standard, or `COMPLETE` if already in the last standard), suggested fee and
   balance to carry.
3. `POST /admin/rollover/apply/` `{board, to_year, items: [{student_id, action, agreed_fee?}], make_current}`.
   Per student (own transaction): `PROMOTE`/`REPEAT` → history row closed + new one, new fee account with the
   old **dues or credit carried forward** (old account becomes `CARRIED_FORWARD`); `LEAVE` → status `LEFT`;
   `COMPLETE` → status `COMPLETED` (old dues stay on the old account). Report of `done` / `failed`
   (`ALREADY_ROLLED_OVER`, `FEE_REQUIRED`, `NOT_ELIGIBLE`, `NO_NEXT_STANDARD`). `WRONG_BOARD_YEAR` if the year
   isn't that board's. `make_current` (default true) makes it the board's current year.

### Reminders
"Ending soon / overdue" show in the fees table now. Automatic SMS/email reminders need a daily job:
switched on at deployment (Phase 8).

## 9b. Dashboards

Logic: `apps/dashboard/services.py`. Every number is computed from the real records on each request
(no stored counters). Money is returned as exact strings (`"26000.00"`).

- `GET /api/v1/staff/dashboard/?board=&days=30` (**admins and teachers**):
  - `students`: active / on hold / left / completed, new admissions in the last `days` (1-366),
    active students per standard, 5 most recent admissions.
  - `learning`: tests in the next 7 days, **tests over but not graded yet**, 5 newest test papers and notes.
  - `fees` (**admins only**, teachers never get this key): for each board's **current** year (or `?board=`):
    accounts, students with pending fees, fully paid, total outstanding, total collected, total credit,
    overdue, ending soon with dues, 5 most recent payments.
- `GET /api/v1/portal/students/{id}/overview/` (parent/student home screen, linked student only, else `404`):
  student details, next 5 upcoming tests, 5 latest results, 5 latest notes, current year's fees
  (total, paid, pending, credit, status, overdue, due date) and pending across all years.
  A student who isn't ACTIVE shows no tests/notes.

## 9c. File storage (Google Drive) and student photos

Logic: `apps/common/storage.py`, commands in `apps/common/management/commands/`.

### Where are files stored?
- **Google Drive** (owner's account, one private folder) once `GOOGLE_DRIVE_CLIENT_ID`, `_CLIENT_SECRET`,
  `_REFRESH_TOKEN` and `_FOLDER_ID` are all set in `.env`; otherwise the local disk (`backend/media`).
  Tests always use local disk.
- Google scope **`drive.file`**: the app sees only files it created, never the rest of the owner's Drive.
- Records store only the key (`gdrive/<drive-file-id>`). Files are **never shared or given public links**:
  the backend downloads them after its own permission checks and streams them (`no-store`).
- Google unreachable, or the connection revoked/expired → `503 FILE_STORAGE_UNAVAILABLE`, and the log says
  to run `python manage.py google_drive_connect` again.

### Setup / maintenance commands
- `python manage.py google_drive_connect`: opens the browser, owner allows access; creates the Drive folder
  (if not set) and writes the refresh token + folder id into `.env` (never printed). Re-run to reconnect.
- `python manage.py migrate_files_to_drive [--dry-run]`: copies files saved on disk before Drive was
  connected (all PDF versions, student photos) into Drive and points the records at them. Safe to re-run.

### Student photos
- Admin: `POST /admin/students/{id}/photo/` (multipart `photo`), `GET` (view), `DELETE` (remove).
- Portal: `GET /portal/students/{id}/photo/` (linked student only, else `404`).
- JPEG/PNG/WebP, max `MAX_PHOTO_SIZE_MB` (5 MB) → `PHOTO_TOO_LARGE`; anything else or fake/corrupt
  images → `INVALID_PHOTO`. Every photo is **re-encoded as a new JPEG**, at most 800 px, with all metadata
  (e.g. GPS location) stripped. Replacing/removing deletes the old file after the change commits. Audited.
- `has_photo` appears in student detail and portal responses.

---

## 10. Cross-cutting gotchas

- **Soft delete is a silent default filter.** `User.objects` hides soft-deleted users;
  `User.all_objects` includes them. A soft-deleted user still owns their email/phone.
- **Every response is `Cache-Control: no-store`** under `/api/`, so the browser's Back button
  can't redisplay private data after logout.
