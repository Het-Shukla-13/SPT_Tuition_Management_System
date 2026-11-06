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

### How do tokens work?
- Access token: 15 min (`JWT_ACCESS_TOKEN_LIFETIME_MINUTES`). Send `Authorization: Bearer <access>`.
- Refresh token: 7 days (`JWT_REFRESH_TOKEN_LIFETIME_DAYS`).
- `POST token/refresh/` `{refresh}` → **rotates**: returns a new refresh token and blacklists
  the old one. Re-using an old refresh token → `401`. Store the new one every time.
- Tokens carry a `role` claim **for the frontend only**. The backend always re-reads the
  role from the database.

### What does logout do?
`POST logout/` `{refresh}` (authenticated) blacklists that refresh token. It is idempotent
(logging out twice is fine). A refresh token that belongs to another user →
`400 INVALID_REFRESH_TOKEN`. The access token stays valid until it expires (≤ 15 min);
the frontend must drop it. Per-device sessions and "log out everywhere" come in Phase 1.2.

### What happens to a soft-deleted or deactivated user's tokens?
Both access and refresh tokens stop working immediately (`401`): authentication looks
the user up through the default manager, which hides soft-deleted users, and checks `is_active`.

---

## 9. Cross-cutting gotchas

- **Soft delete is a silent default filter.** `User.objects` hides soft-deleted users;
  `User.all_objects` includes them. A soft-deleted user still owns their email/phone.
- **Every response is `Cache-Control: no-store`** under `/api/`, so the browser's Back button
  can't redisplay private data after logout.
