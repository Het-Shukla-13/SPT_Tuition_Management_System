# Backend FAQ: business logic behind the API

This documents the behaviour you would otherwise have to read the code to learn:
silent defaults, gating rules, status semantics and edge cases. **Update it in the
same change whenever you add or change such logic** (a stale entry is worse than none).

All endpoints are under `/api/v1/`. Every response uses the envelope
`{success, message, data, errors, error_code, meta}`.

---

## 1. Authentication (`/api/v1/auth/`)

### How does a user sign up or log in?
Passwordless, with a one-time code (OTP) by email or SMS:

1. `POST otp/request/` `{channel: EMAIL|PHONE, identifier, purpose: REGISTER|LOGIN}`
2. `POST otp/verify/` `{channel, identifier, purpose, code}` → `{access, refresh, user}`

Logic: `apps/accounts/services/otp.py`.

### Does `otp/request/` tell me whether an account exists?
No, by design (spec §10.1, account enumeration). The response is always the same
`200 "If the details are valid, a verification code has been sent."`:

| Purpose | Account exists? | What actually happens |
|---|---|---|
| REGISTER | no | OTP sent |
| REGISTER | yes (incl. soft-deleted) | No OTP; an "you already have an account" notice is sent to that email/phone |
| LOGIN | yes, active | OTP sent |
| LOGIN | no / inactive / soft-deleted | Nothing sent |

Cooldowns and limits also apply identically in every row, so they reveal nothing either.

### Can a LOGIN code create an account, or a REGISTER code log in?
No. A code only works for the `purpose` (and `channel` + `identifier`) it was issued for.

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
| `ACCOUNT_ALREADY_EXISTS` | 409 | REGISTER, but the identity got registered meanwhile |
| `ACCOUNT_DISABLED` | 403 | LOGIN, but the account was deactivated after the code was sent |

### What happens if the email/SMS can't be sent?
`503 OTP_DELIVERY_FAILED`, and the unsent code is invalidated. We never claim
success for a code nobody received. (Exception: a failed "already registered" notice
is swallowed, because reporting it would reveal that the account exists.)

### What if the cache (rate-limit store) is down?
**Fail closed**: OTP requests return `503 OTP_TEMPORARILY_UNAVAILABLE` and the OTP
endpoints' IP throttle returns `503 THROTTLE_UNAVAILABLE` (`Retry-After: 30`). Losing the
limits must not mean unlimited OTP emails or guesses. The global anon/user throttles
**fail open** (they only smooth load). See `apps/common/throttling.py`.

### How are phone numbers and emails normalised?
Before storage, lookup and rate-limiting (`apps/accounts/identifiers.py`):
- Email: trimmed + lowercased.
- Phone: spaces/dashes/brackets removed, `00` → `+`, a bare 10-digit number gets
  `DEFAULT_PHONE_COUNTRY_CODE` (`+91`), result must be E.164 (`+919876543210`).

### What role does a new account get? Can I sign up as ADMIN?
Always `STUDENT`. Any `role` in the payload is ignored. ADMIN accounts are created
only with `python manage.py createsuperuser`.

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
| `STUDENT` | Students | Public OTP sign-up (always STUDENT) |
| `ADMIN` | Institute staff | Promoted by the owner via `POST admin/users/{id}/role/` |
| `ADMIN` + `is_superuser` ("owner") | The institute owner(s) | Only `python manage.py createsuperuser` |

Permission classes live in `apps/common/permissions.py`: `IsAdmin`, `IsStudent`,
`IsSuperUser` (owner), and object-level `IsOwnerOrAdmin`.

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
(e.g. `{"role": ["STUDENT", "ADMIN"]}`), IP and request ID. Read-only in Django admin.

---

## 9. Cross-cutting gotchas

- **Soft delete is a silent default filter.** `User.objects` hides soft-deleted users;
  `User.all_objects` includes them. A soft-deleted user still owns their email/phone.
- **Every response is `Cache-Control: no-store`** under `/api/`, so the browser's Back button
  can't redisplay private data after logout.
