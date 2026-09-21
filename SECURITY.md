# Security

A summary of DUKANI POS's actual security posture — what's enforced, how,
and where the known gaps are. Written from direct knowledge of the
codebase, not a generic checklist.

## Authentication

- Bearer JWT access tokens (short-lived) + refresh tokens (long-lived),
  both stored client-side in `localStorage` — a deliberate architecture
  choice, not an oversight (see [Known limitations](#known-limitations)
  for the tradeoff).
- Refresh is single-session-per-user by design: `users.current_refresh_jti`
  holds exactly one valid refresh token at a time. Logging in on a new
  device silently invalidates the previous session's refresh token — there
  is no multi-device session list because there's nothing to list.
- Logout, password change, and password reset all bump `token_version` and
  clear `current_refresh_jti`, which instantly invalidates every
  outstanding token for that user without needing a server-side revocation
  table.
- Account lockout: `MAX_LOGIN_ATTEMPTS` failed attempts locks the account
  for `LOCKOUT_MINUTES`, tracked server-side (`failed_login_attempts`,
  `locked_until` on the `users` row) — not bypassable from the client.
- Password policy (`app/core/security.py::validate_password_strength`):
  minimum 8 characters, at least one uppercase, one lowercase, one digit,
  and rejected outright if it matches a small denylist of the most common
  weak passwords (`password123`, `admin123`, etc. — case-insensitive,
  ignoring trailing digits/punctuation).
- `forgot-password` always returns the same response regardless of whether
  the email matched an account — deliberate anti-enumeration. The same
  pattern is used for `GET /sales/{id}` (a cashier looking up someone
  else's sale gets 404, not 403 — a 403 would confirm the sale exists).

## Authorization — branch isolation is enforced server-side, not by the UI

The frontend's role/permission checks (`utils/permissions.js`) exist to
build a sensible UI, not to enforce anything — every branch-scoping and
role-gating decision is re-checked independently in the backend, and the
backend is the only thing that's actually trusted:

- `app/core/authorization.py` is the single source of truth for "what
  branch(es) may this user read/write". `branch_context` (a FastAPI
  dependency) resolves the effective branch for reads; `
  require_write_branch_access` gates writes. Global-scope roles
  (`super_admin`, `admin`, `general_manager`) can select any branch or
  "ALL"; `cashier` is hard-locked to their own `branch_id`; `store_keeper`
  is hard-locked to whichever branch currently has `branch_type ==
  'main_store'` (resolved fresh per request, never cached/trusted from the
  user row).
- A DB-level partial unique index guarantees at most one active
  `main_store` branch can ever exist — `store_keeper`'s entire scope
  depends on that being true, and without the constraint a second one
  (e.g. from a bad seed/import) would crash every store_keeper-touching
  request with a raw `MultipleResultsFound` instead of a clean error.
- Role hierarchy for user management: `admin` cannot create, edit,
  deactivate, unlock, or permanently delete an `admin` or `super_admin`
  account — checked server-side (`HIDDEN_FROM_ADMIN` in
  `user_service.py`), not just hidden from the UI.
- No self-service escalation path: nobody (including `super_admin`) can
  change their own role, branch, or active-state through the admin
  user-management surface — that's `PUT /auth/me` (name/email/password
  only), a structurally separate endpoint.

## Rate limiting

In-process (`slowapi`, `storage_uri="memory://"`) — not shared across
gunicorn workers (2 workers in production), resets on restart. An accepted
tradeoff, not an oversight: adding Redis back for this alone was
explicitly decided against earlier in this project's history. Currently
rate-limited: `/auth/login`, `/auth/refresh`, `/auth/forgot-password`,
`/auth/reset-password`, `/users/{id}/unlock` — all at the same
`RATE_LIMIT_LOGIN` setting (5/minute by default). `/users/{id}/unlock` in
particular matters: at the previous 100/minute default it could have
outrun the 5-attempt lockout it exists to enforce if an admin token were
ever compromised.

## Transport and headers

- Both `pos.cctvpoint.org` and `demo.cctvpoint.org` are reached only
  through a Cloudflare Tunnel — no inbound port is open on the server at
  all, so there's no direct-IP attack surface to begin with.
- `ENABLE_HSTS=true` in both production `.env` files.
- `CORS_ORIGINS` is the exact production origin(s), never `["*"]`, in both
  environments.
- `SecurityHeadersMiddleware` (`app/core/middleware.py`) sets the standard
  security headers on every response; Nginx additionally strips the
  `Server` version header (`server_tokens off`), and uvicorn's own
  `Server` header carries no version string by default.
- Pure Bearer-token auth means this API is inherently CSRF-immune — there's
  no ambient credential (cookie) a cross-site request could ride on.

## Data isolation and correctness (indirectly security-relevant)

- Every business-consistency fix from Phase 1/2 of this project's
  hardening pass is also an isolation guarantee: a cashier's `GET /sales`
  was, before this pass, unfiltered by branch for their own role in one
  code path — closed. `GET /products/{id}` leaked every branch's stock
  levels to any authenticated user regardless of role — closed. See git
  history for the complete list; this file summarizes the current state,
  not the changelog.
- All queries are parameterized ORM/Core constructs — no raw string-built
  SQL anywhere in the codebase, so there is no SQL-injection surface to
  audit endpoint-by-endpoint.
- Concurrency: money- and stock-affecting writes (sale void, daily closing,
  transfer approval/execution, inventory adjustment) use row-level locking
  (`SELECT ... FOR UPDATE`) and/or DB unique constraints with clean
  conflict handling, verified by dedicated true-concurrency tests (real
  cross-connection races, not simulated) — see
  `backend/tests/test_*_true_concurrency.py`.

## Secret management

- `backend/.env` (both environments) is gitignored and never committed;
  confirmed via full git history search, not just the working tree.
- `frontend/.env` **is** intentionally committed — it holds only
  `VITE_API_BASE_URL=http://localhost:8000`, a local-dev default with no
  secret in it. `frontend/.env.local` and `frontend/.env.production` are
  the ones that could carry real values and are correctly gitignored.
- `deploy/validate_release.sh` scans both the current git tree and full
  git history for secret-shaped filenames (`.pem`, `.key`, `.ppk`, `.pfx`,
  `id_rsa*`, `id_ed25519*`, any `.env` other than the one known-safe
  exception above) before a release — see `DEPLOYMENT.md`. This exists
  because of a real near-miss: a manually-built archive once included a
  real private key that was never committed to git but would have shipped
  in a distributable snapshot had it not been caught.

## Reporting a vulnerability

This is an internal business system, not a public product — report any
security concern directly to whoever operates `pos.cctvpoint.org`, not
through a public issue tracker.

## Known limitations

Listed honestly rather than omitted:

- **Tokens in `localStorage`, not httpOnly cookies.** A successful XSS
  anywhere in the frontend could exfiltrate a token. This is a real
  architecture tradeoff that was explicitly evaluated and deferred — a
  cookie-based migration is a genuine architecture change (CORS/CSRF
  posture changes, both live domains need coordinated testing) and was
  deliberately scoped out of this hardening pass rather than rushed.
- **No idempotency protection beyond `POST /sales`.** Other write
  endpoints (transfers, closings) don't yet have `Idempotency-Key` support
  — a network retry there could still double-submit. Sales was prioritized
  as the highest-value/highest-frequency case.
- **No automated dependency vulnerability scanning** (`pip-audit`/`npm
  audit` are not run in any pipeline — there is no CI pipeline at all yet,
  see `DEPLOYMENT.md`'s Known gaps).
- **No WAF / DDoS protection beyond whatever Cloudflare's tunnel provides
  by default** — not separately configured or verified.
- **Rate limiting is in-process only**, see above — a distributed
  brute-force spread across enough requests to stay under 5/minute per
  worker isn't caught by the current setup.
