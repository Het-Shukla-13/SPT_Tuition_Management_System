# Phase 1.5: password login + trusted devices

Decided with the owner (2026-11-09). Replaces "email code every login".

## Rules

| Login | Trusted device | New device |
|---|---|---|
| Email + password | password → logged in | password → emailed code → logged in, device trusted |
| Google | one tap → logged in | one tap → emailed code → logged in, device trusted |
| Phone | SMS code every time (no password, no device trust) | same |

- First password and forgotten password: one flow. Email → code → new password →
  logged in, device trusted. The office never sees or sets passwords.
- A device stays trusted for `TRUSTED_DEVICE_DAYS` (90) from the code check,
  across logouts. Trust is removed by: changing the password (all other
  devices), resetting the password (all devices), "log out of all devices",
  deactivation, role change, or removing it from the trusted-devices list.
- Staying logged in (sessions, refresh cookie, 30-day max) is unchanged.
- Email-code-only login is removed: a code can never replace the password.

## Data

`TrustedDevice` (`trusted_devices`): user, token_hash (SHA-256 of a random
256-bit token; the raw token only ever lives in the browser cookie), label (user
agent), ip, expires_at, last_used_at, revoked_at, revoked_reason.
Unique (user, token_hash): one browser can be trusted by several family members.

Cookie `tms_device`: HttpOnly, Secure (prod), SameSite=Lax, path `/api/v1/auth/`,
90 days. Same protections as the refresh cookie.

## Endpoints (`/api/v1/auth/`)

| Endpoint | Body | Result |
|---|---|---|
| `POST login/` | email, password | `AUTHENTICATED` + tokens, or `OTP_REQUIRED` + `login_ticket` |
| `POST login/verify/` | login_ticket, code | tokens; device trusted |
| `POST login/resend/` | login_ticket | a new code (cooldowns apply) |
| `POST password/reset/` | email | "if the email exists, a code was sent" |
| `POST password/reset/confirm/` | email, code, new_password | tokens; device trusted; every other session and device ended |
| `POST password/change/` (logged in) | current_password, new_password | other sessions ended, other devices untrusted |
| `GET devices/`, `DELETE devices/{id}/` (logged in) | | list / remove trusted devices |

`otp/request` + `otp/verify` remain for PHONE only. Google: `google/` returns
`OTP_REQUIRED` on an untrusted device even for a linked account; `google/verify/`
completes it (the id_token binds the code to that browser).

## Why a login ticket

The new-device code is emailed only after a correct password. Without binding,
someone who can read the user's inbox (but doesn't know the password) could take
a code the real user just requested and finish the login on their own device.
`login/` returns a signed, short-lived `login_ticket` (user id + random nonce);
the challenge stores the nonce; `login/verify/` needs both ticket and code.

## Abuse protection

- Wrong email/password → one generic `INVALID_CREDENTIALS` (also for accounts
  with no password yet, unknown emails, deleted accounts). A dummy hash check
  keeps timing equal.
- `LOGIN_MAX_FAILURES` (5) failures for an email → `LOGIN_LOCKED` for
  `LOGIN_LOCKOUT_SECONDS` (15 min), counted per email (works the same for
  unknown emails, so lockout doesn't reveal accounts). Plus a per-IP throttle.
- Password rules: Django validators (min 8, not common, not all digits, not
  similar to the name/email).
- Codes: existing OTP limits (cooldown, hourly cap, 5 attempts, 5-minute expiry).
