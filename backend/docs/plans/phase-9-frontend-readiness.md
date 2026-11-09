# Phase 9 — Frontend integration readiness

Goal: the frontend can be built against a stable, documented, consistent API
with a secure login model, without the backend changing underneath it.

Spec items: final API contracts · consistent responses · pagination and
filtering · authentication integration · error handling · redirect and
refresh behaviour · end-to-end testing.

## 1. Authentication integration: refresh token in an HttpOnly cookie

### Problem
Login and refresh return `{access, refresh}` in the JSON body. A browser app
would have to store the 7-day refresh token where JavaScript can read it
(localStorage). Any XSS bug, or a malicious npm package in the frontend build,
could then steal it and stay logged in as that parent/admin for days.

### Design
- **Access token** (15 min): returned in the body as today. The frontend keeps
  it **in memory only** (a JS variable), never in storage.
- **Refresh token**: set as a cookie the browser stores but JavaScript can't read:
  - `HttpOnly; Secure (production); SameSite=Lax; Path=/api/v1/auth/`
  - `Path` limits it to auth endpoints: it's never sent with ordinary API calls.
  - `Max-Age` = refresh lifetime; re-set on every rotation.
- `POST auth/token/refresh/` reads the cookie (body still accepted, for
  Swagger/tests/future mobile app). Response sets the rotated cookie.
- `POST auth/logout/` and `logout-all/` clear the cookie.
- `REFRESH_TOKEN_IN_BODY` setting: `True` in development (Swagger keeps
  working as today), `False` in production (the token is only in the cookie).
- **Page reload**: the in-memory access token is gone, so the app calls
  `token/refresh/` on startup; the cookie silently logs the user back in.

### CSRF protection for the cookie
A cookie is sent automatically, so another site could try to make the browser
call `token/refresh/` or `logout/`. When the refresh token comes **from the
cookie**, these endpoints require the header `X-Requested-With: XMLHttpRequest`.
Browsers only let another site send a custom header after a CORS preflight,
which only our frontend origin passes. Missing header → `403 CSRF_HEADER_MISSING`.

### Deployment consequence (decided in 8b)
`SameSite=Lax` cookies only work when the frontend and API are the **same
site** (same registrable domain). Safari blocks cross-site cookies entirely.
- With a domain: `app.example.in` + `api.example.in` → same site. ✓
- Without a domain: Caddy serves the built frontend **and** proxies `/api/`
  on one hostname (e.g. `spt-tuition.duckdns.org`) → same origin, no CORS. ✓
- ✗ `x.pages.dev` + `y.duckdns.org`: different sites; the cookie would be
  blocked on iPhones. So "Cloudflare Pages without a domain" is ruled out.

## 2. Consistent responses
Every JSON answer from `/api/` is the envelope
`{success, message, data, errors, error_code, meta}`, including errors raised
outside DRF views: unknown URLs (404), bad Host header (400), CSRF failures
(403), crashes in middleware (500). Django's HTML error pages must never reach
the frontend. Enforced by a test over every endpoint x role x method.

## 3. Pagination and filtering
- All list endpoints: `?page=&page_size=` (max 100), `meta` carries
  `page, page_size, total_count, total_pages, has_next, has_previous`.
- Survey results and any fixes recorded in `docs/frontend/api-guide.md`
  (per list: filters, search, ordering).

## 4. Error handling
- `docs/frontend/error-codes.md`: every `error_code`, its HTTP status and what
  the UI should do (show message / redirect to login / retry later / fix form).
- A test fails if a new `error_code` is added to the code but not to the doc.

## 5. Redirect and refresh behaviour (frontend contract)
- Any `401` on a normal call → refresh once (single shared refresh for all
  pending calls) → retry the call. Refresh fails → clear state, go to login
  (remember the page to return to).
- `403` → stay, show "not allowed". Never retry.
- Several tabs: refresh-token rotation already allows concurrent refreshes in
  a 30 s grace window; logout broadcasts to other tabs (BroadcastChannel).
- After a forced logout (session revoked, role changed, account deactivated)
  the refresh fails with a specific `error_code`, so the login page can say why.

## 6. End-to-end tests
Whole journeys through the HTTP API (no internals), in `apps/e2e/` tests:
1. Admin invites a parent while admitting two children → parent logs in by
   email OTP (cookie flow) → sees both children → switches child → sees tests,
   notes, fees.
2. Teacher uploads a test + answer key, assigns it, records marks → parent sees
   the marks; the answer key unlocks only after the test ends.
3. Session lifecycle: login → reload (refresh via cookie) → logout → refresh
   fails; admin deactivates a user → their next refresh fails.
