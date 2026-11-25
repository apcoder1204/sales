# Send Reports to WhatsApp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Tuma WhatsApp" button on every report and day closing that delivers the report PDF to one designated WhatsApp number through a self-hosted OpenWA gateway.

**Architecture:** The browser builds the PDF (existing jsPDF code) and uploads it to a new backend endpoint. The backend checks the role, PDF, daily cap and duplicates, then forwards it to OpenWA (`127.0.0.1:2785`, Docker, Baileys engine) with the API key held server-side, and audit-logs the send. The receiver number is stored in a new `app_settings` table (prod) or pinned by env var (demo).

**Tech Stack:** FastAPI + async SQLAlchemy + Alembic + httpx (backend), React 18 + Vite + jsPDF (frontend), OpenWA `ghcr.io/rmyndharis/openwa` in Docker.

**Spec:** `docs/superpowers/specs/2026-11-25-whatsapp-report-sharing-design.md`

## Global Constraints

- OpenWA API key never sent to the browser; receiver number only ever read server-side.
- Datetimes written to TIMESTAMP columns use `.replace(tzinfo=None)`; use `app.core.business_time` helpers (`utcnow`, `business_date_today`, `utc_range_for_business_date`).
- No enum-alter migrations: audit entries use the existing category `"system"`.
- Errors raise `AppException` subclasses with a stable `code`; every new code gets a message in both `frontend/src/constants/translations/sw.js` and `en.js` under `makosa.msimbo`.
- All new UI strings go in both translation files (Swahili primary).
- `httpx` moves from `requirements-dev.txt` to `requirements.txt` (`httpx==0.28.1`).
- Config defaults: `WHATSAPP_ENABLED=False`, `OPENWA_BASE_URL="http://127.0.0.1:2785/api"`, `OPENWA_API_KEY=""`, `OPENWA_SESSION_ID=""`, `OPENWA_TIMEOUT_SECONDS=30`, `WHATSAPP_DAILY_CAP=50`, `WHATSAPP_RECEIVER_OVERRIDE=""`, `WHATSAPP_CAPTION_PREFIX=""`.
- Demo env: `WHATSAPP_DAILY_CAP=15`, `WHATSAPP_CAPTION_PREFIX="[DEMO] "`, `WHATSAPP_RECEIVER_OVERRIDE=<receiver>`.
- PDF upload cap 10 MB; must start with `%PDF`.
- Duplicate window 10 minutes (same SHA-256, status `sent`).
- npm is not on PATH on the dev box: frontend commands use `node node_modules/.bin/vite …`.
- Backend tests: `cd backend && .venv/bin/pytest`. Tests never hit a real gateway (override the gateway dependency).
- Pushing to `main` auto-deploys prod and demo: get the user's explicit go-ahead immediately before any push.

## Review Focus

1. **Double-click / two staff sending the same closing at once** → exactly one WhatsApp message; the second gets "Ripoti hii imeshatumwa". Pinned in Task 3 (`test_duplicate_pdf_refused`) and by the advisory lock.
2. **Gateway down, phone logged out, or slow** → a specific error, an audit entry, and reports/downloads unaffected; `/whatsapp/status` never 500s. Pinned in Task 2 (`test_status_when_gateway_unreachable`) and Task 3 (`test_timeout_reports_unknown`).
3. **Number typed in local formats** (`0712 345 678`, `+255 712 345 678`, `255712345678`) all store `255712345678`; junk is refused. Pinned in Task 1 (`test_normalize_phone_*`).
4. **A non-PDF or oversized upload** → 400 or 413, nothing sent. Pinned in Task 3 (`test_rejects_non_pdf`, `test_rejects_oversize`).
5. **A cashier passing another branch's `branch_id`** → the caption names their own branch. Pinned in Task 3 (`test_cashier_caption_uses_own_branch`).

---

### Task 1: Receiver setting — config, `app_settings` table, phone normalisation, settings API

**Files:**
- Modify: `backend/app/config.py` (add the config keys from Global Constraints)
- Modify: `backend/requirements.txt`, `backend/requirements-dev.txt` (move httpx)
- Create: `backend/app/models/app_setting.py`; register in `backend/app/db/base.py`
- Create: `backend/alembic/versions/<rev>_add_app_settings_table.py` (down_revision `e5c2670d4b7c`)
- Create: `backend/app/services/whatsapp_service.py` (settings part)
- Create: `backend/app/schemas/whatsapp.py`
- Create: `backend/app/api/v1/whatsapp.py`; register in `backend/app/api/v1/router.py`
- Modify: `backend/app/core/exceptions.py`
- Test: `backend/tests/test_whatsapp_settings.py`

**Interfaces:**
- Produces:
  - Model `AppSetting(key: str PK String(100), value: Text not null, updated_by: UUID|None FK users.id SET NULL, updated_at: TIMESTAMP server_default now)`, table `app_settings`.
  - `RECEIVER_KEY = "whatsapp_report_number"`
  - `normalize_phone(raw: str) -> str` raises `ValidationException(code="INVALID_PHONE")`.
  - `async get_receiver(db) -> tuple[str | None, bool]` → `(number, locked)`. `locked` is True when `settings.WHATSAPP_RECEIVER_OVERRIDE` is set, in which case the number is `normalize_phone(override)`.
  - `async set_receiver(db, raw: str, user) -> str`. Raises `WhatsAppReceiverLockedException` (403, code `WHATSAPP_RECEIVER_LOCKED`) when locked. Upserts the row and writes audit action `whatsapp.set_receiver`, category `system`.
  - Schemas: `WhatsAppSettingsResponse{number: str|None, locked: bool, enabled: bool, connected: bool}`, `WhatsAppSettingsUpdate{number: str}`.
  - Routes `GET /api/v1/whatsapp/settings` and `PUT /api/v1/whatsapp/settings`, both `require_role("super_admin", "admin")`. In this task `connected` is always `False`; Task 2 wires it.

- [ ] **Step 1: Write failing tests** in `test_whatsapp_settings.py`:
  - `test_normalize_phone_local_formats`: `normalize_phone("0712 345 678") == normalize_phone("+255 712-345-678") == normalize_phone("255712345678") == "255712345678"`; `normalize_phone("00255712345678") == "255712345678"`.
  - `test_normalize_phone_rejects_junk`: `"abc"`, `"0712"`, `""`, `"+1234"` (fewer than 10 digits), and a 16-digit number each raise `ValidationException`.
  - Rule: strip spaces, dashes and parentheses; a leading `+` or `00` is dropped; a leading single `0` with 10 digits total becomes `255` + the rest; the result must be 10–15 digits.
  - `test_admin_sets_and_reads_receiver`: PUT `{"number": "0712345678"}` as admin → 200, `number == "255712345678"`; a following GET returns the same and `locked is False`.
  - `test_cashier_cannot_read_or_set_settings`: GET and PUT as cashier → 403.
  - `test_override_locks_receiver` (monkeypatch `settings.WHATSAPP_RECEIVER_OVERRIDE = "+255700000001"`): GET → `number == "255700000001"`, `locked is True`; PUT → 403 with code `WHATSAPP_RECEIVER_LOCKED`.
  - `test_set_receiver_is_audited`: after PUT, an `AuditLog` row exists with `action == "whatsapp.set_receiver"`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_whatsapp_settings.py -v`. Expected: FAIL (import errors).
- [ ] **Step 3: Implement** the model, migration (mirror `e5c2670d4b7c_add_idempotency_keys_table.py` style), config keys, requirements move, exception class, service functions, schemas, routes and router registration.
- [ ] **Step 4: Migrate and run.** `.venv/bin/alembic upgrade head`, then `.venv/bin/pytest tests/test_whatsapp_settings.py -v`. Expected: all PASS. Then run the full `.venv/bin/pytest -q` to confirm nothing else broke.
- [ ] **Step 5: Commit** — `feat(whatsapp): receiver number setting and app_settings table`.

### Task 2: OpenWA gateway client + status endpoint (confirm the API against a real local container first)

**Files:**
- Create: `deploy/openwa/docker-compose.yml`, `deploy/openwa/.env.example`
- Create: `backend/app/services/whatsapp_gateway.py`
- Modify: `backend/app/services/whatsapp_service.py`, `backend/app/api/v1/whatsapp.py`, `backend/app/schemas/whatsapp.py`
- Test: `backend/tests/test_whatsapp_gateway.py`

**Interfaces:**
- Consumes: Task 1 settings/config.
- Produces:
  - `class WhatsAppGateway(base_url: str, api_key: str, session_id: str, timeout: float, transport: httpx.AsyncBaseTransport | None = None)`
    - `async session_status() -> str`: the OpenWA session status string (`"ready"`, `"qr_ready"`, …). Returns `"unreachable"` on connection error or timeout. Never raises.
    - `async send_document(phone: str, pdf: bytes, filename: str, caption: str) -> None`. Raises `GatewayTimeout`, `GatewayUnreachable`, `GatewaySessionNotReady` or `GatewayRejected(status_code, body)`, all subclasses of `GatewayError`.
  - `def get_whatsapp_gateway() -> WhatsAppGateway`: FastAPI dependency built from settings; tests override it.
  - `GET /api/v1/whatsapp/status` → `WhatsAppStatusResponse{enabled: bool, configured: bool, connected: bool}`. Roles: `super_admin, admin, general_manager, store_keeper, cashier`. `connected = enabled and status == "ready"`; the gateway is not called when `WHATSAPP_ENABLED` is false.
  - `GET /settings` now fills `connected` the same way.

- [ ] **Step 1: Run OpenWA locally and pin the API.** Write `deploy/openwa/docker-compose.yml`: one service `openwa`, image `ghcr.io/rmyndharis/openwa:<pinned tag>` (use the latest release tag; record its digest in a comment), `ENGINE_TYPE=baileys`, `API_MASTER_KEY=${OPENWA_API_KEY}`, `SEND_PACING_ENABLED=true`, `NODE_ENV=production`, `ENABLE_SWAGGER=true` (local only, set via `.env`), named volume `openwa-data:/app/data`, port `127.0.0.1:2785:2785`, `restart: unless-stopped`. Run `docker compose -f deploy/openwa/docker-compose.yml --env-file deploy/openwa/.env up -d`, open `http://127.0.0.1:2785/api/docs`, and record in a comment at the top of `whatsapp_gateway.py`: the exact session-status path and response field, the exact send-document path, the request field names, and the response on success. Expected: the paths are confirmed (`POST /sessions/{id}/messages/send-document` with `chatId`/`base64`/`mimetype`/`filename`/`caption` is the expectation; adapt if Swagger differs). Note that `ENGINE_TYPE`'s value for Baileys is confirmed too.
- [ ] **Step 2: Write failing tests** using `httpx.MockTransport`:
  - `test_send_document_payload`: asserts method, path `/sessions/S1/messages/send-document`, header `X-API-Key: k`, and JSON `chatId == "255712345678@c.us"`, `mimetype == "application/pdf"`, base64 that decodes to the input bytes, plus `filename` and `caption`.
  - `test_send_document_errors`: 5xx → `GatewayRejected`; `httpx.ConnectError` → `GatewayUnreachable`; `httpx.ReadTimeout` → `GatewayTimeout`; a response saying the session isn't ready (shape from Step 1) → `GatewaySessionNotReady`.
  - `test_status_when_gateway_unreachable`: transport raises `ConnectError` → `session_status() == "unreachable"`, and `GET /whatsapp/status` (gateway dependency overridden, `WHATSAPP_ENABLED=True`) returns 200 `{connected: false}`.
  - `test_status_disabled_skips_gateway`: with `WHATSAPP_ENABLED=False`, the endpoint returns `enabled: false` and the mock transport is never called.
- [ ] **Step 3: Run** `.venv/bin/pytest tests/test_whatsapp_gateway.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement** `whatsapp_gateway.py`, the status endpoint and the `connected` wiring.
- [ ] **Step 5: Run.** Run the gateway tests, then `.venv/bin/pytest -q`. Expected: all PASS.
- [ ] **Step 6: Commit** — `feat(whatsapp): OpenWA gateway client, status endpoint, compose file`. Do not commit `deploy/openwa/.env`; add it to `.gitignore`.

### Task 3: `POST /whatsapp/send-report`

**Files:**
- Modify: `backend/app/services/whatsapp_service.py`, `backend/app/api/v1/whatsapp.py`, `backend/app/core/exceptions.py`
- Test: `backend/tests/test_whatsapp_send_report.py`

**Interfaces:**
- Consumes: `get_receiver`, `WhatsAppGateway.send_document`, `GatewayError` subclasses, `resolve_read_branch_id`, `audit_service.log`.
- Produces:
  - `REPORT_TYPE_ROLES: dict[str, tuple[str, ...]]`, copied from the existing read gates:
    - `sales`, `branch_performance`, `cashier_performance`, `profit_loss` → super_admin, admin, general_manager
    - `inventory`, `low_stock`, `inventory_valuation` → super_admin, admin, general_manager, store_keeper
    - `stock_movements` → super_admin, admin, general_manager, store_keeper, cashier
    - `closing` → super_admin, admin, general_manager, cashier
  - `async send_report(db, user, gateway, *, pdf: bytes, report_type: str, title: str, period_label: str, branch_id: UUID | None, ip: str | None) -> None`
  - Route `POST /api/v1/whatsapp/send-report`, multipart with fields `file`, `report_type`, `title` (≤120 chars), `period_label` (≤60 chars) and optional `branch_id`. Returns `{"status": "sent"}`.
  - Error codes and statuses:

    | Code | Status |
    |---|---|
    | `WHATSAPP_DISABLED` | 503 |
    | `WHATSAPP_NO_RECEIVER` | 400 |
    | `WHATSAPP_NOT_CONNECTED` | 503 (session not ready or unreachable) |
    | `WHATSAPP_SEND_FAILED` | 502 |
    | `WHATSAPP_TIMEOUT` | 504 |
    | `WHATSAPP_DAILY_CAP` | 429, `params: {cap}` |
    | `WHATSAPP_DUPLICATE` | 409 |
    | `WHATSAPP_INVALID_PDF` | 400 |
    | `WHATSAPP_PDF_TOO_LARGE` | 413 |
    | unknown `report_type` / role not allowed | `InsufficientPermissionException` |

- **Order inside `send_report`:**
  1. Enabled.
  2. Role allowed for the report type.
  3. PDF checks: ≤10 MB and starts with `%PDF`.
  4. Receiver set.
  5. `SELECT pg_advisory_xact_lock(715001)` (serialises sends so the cap and duplicate checks are exact).
  6. Daily cap: count `AuditLog` rows with `action == "whatsapp.send_report"` and `details["status"] == "sent"` whose `created_at` falls in `utc_range_for_business_date(business_date_today())`.
  7. Duplicate: same `details["sha256"]` with status `sent` in the last 10 minutes.
  8. Build the caption.
  9. `gateway.send_document`.
  10. Write the audit entry for every outcome that reaches step 9: `action "whatsapp.send_report"`, `category "system"`, `branch_id` set to the resolved branch, and `details {report_type, title, period_label, sha256, status: "sent"|"failed"|"unknown", error_code?}`. A timeout is recorded as `unknown`. The audit commit releases the lock.
  11. Raise the mapped error, if any.
- **Caption** (exact copy):
  ```
  {WHATSAPP_CAPTION_PREFIX}*{title}*
  {branch name, if a branch resolved}
  {period_label}
  Imetumwa na: {user.full_name}
  ```
  - Strip control characters from `title` and `period_label`.
  - The branch comes from `resolve_read_branch_id(db, user, branch_id)`; no line when it resolves to None.
- **Filename:** sanitised from `file.filename`. Fall back to `ripoti.pdf`.

- [ ] **Step 1: Write failing tests.** Override `get_whatsapp_gateway` with a fake that records calls and can be set to raise. Set the receiver via `set_receiver`, and set `WHATSAPP_ENABLED=True` via monkeypatch.
  - `test_admin_sends_report`: 200, exactly one gateway call to `"255712345678"`, the caption contains `"*Ripoti ya Mauzo*"` and `"Imetumwa na: "`, and an audit row has `status "sent"` and a 64-hex `sha256`.
  - `test_cashier_cannot_send_sales_report`: 403, no gateway call.
  - `test_cashier_caption_uses_own_branch`: a cashier in branch A sends a `closing` with `branch_id = B` → the caption contains A's name and not B's.
  - `test_rejects_non_pdf` (bytes `b"hello"` → 400 `WHATSAPP_INVALID_PDF`) and `test_rejects_oversize` (10 MB + 1 → 413). No gateway call in either.
  - `test_no_receiver` → 400 `WHATSAPP_NO_RECEIVER`. `test_disabled` → 503 `WHATSAPP_DISABLED`.
  - `test_duplicate_pdf_refused`: two sends of the same bytes → the second is 409 `WHATSAPP_DUPLICATE`; one gateway call in total.
  - `test_daily_cap`: with `WHATSAPP_DAILY_CAP=2`, three different PDFs → the third is 429; two gateway calls.
  - `test_timeout_reports_unknown`: the fake raises `GatewayTimeout` → 504 `WHATSAPP_TIMEOUT`, audit status `unknown`.
  - `test_not_connected`: the fake raises `GatewaySessionNotReady` → 503 `WHATSAPP_NOT_CONNECTED`, audit status `failed`.
  - `test_demo_prefix`: `WHATSAPP_CAPTION_PREFIX="[DEMO] "` → the caption starts with `"[DEMO] *"`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_whatsapp_send_report.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** per the interfaces above.
- [ ] **Step 4: Run** these tests, then `.venv/bin/pytest -q`. Expected: all PASS.
- [ ] **Step 5: Live check against the local OpenWA.** Link the local container to the sender phone (needs the user: a QR scan; or skip and do this at Task 6). Set the receiver, then `curl -F file=@<some>.pdf -F report_type=sales -F title=Test -F period_label=Leo` with an admin token to `/api/v1/whatsapp/send-report`. Expected: the PDF arrives on the receiver phone.
- [ ] **Step 6: Commit** — `feat(whatsapp): send-report endpoint with cap, dedupe and audit`.

### Task 4: Frontend — PDF as blob, service, "Tuma WhatsApp" button on reports and closings

**Files:**
- Modify: `frontend/src/utils/reportExport.js`
- Create: `frontend/src/services/whatsappService.js`
- Create: `frontend/src/hooks/useWhatsAppStatus.js`
- Create: `frontend/src/components/ui/SendWhatsAppButton.jsx`
- Modify: `frontend/src/features/reports/ReportsPage.jsx`, `frontend/src/features/closing/ClosingPage.jsx`
- Modify: `frontend/src/constants/translations/sw.js`, `en.js`

**Interfaces:**
- Consumes: `GET /whatsapp/status`, `POST /whatsapp/send-report`, the error codes from Task 3.
- Produces:
  - `export async function buildPDF(type, data, period) -> Promise<{ blob: Blob, filename: string, title: string, periodLabel: string }>`. `downloadPDF` becomes `buildPDF` plus a save of the same blob/filename. PDF output is unchanged.
  - `whatsappService.getStatus()`, `.getSettings()`, `.updateSettings(number)`, `.sendReport({ blob, filename, reportType, title, periodLabel, branchId })`. The last one sends multipart `FormData`.
  - `useWhatsAppStatus() -> { enabled, configured, connected, loading, refresh }`. Module-level cache with a 60 s TTL so a page with many rows makes one request.
  - `<SendWhatsAppButton reportType getPdf={() => buildPDF(...)} branchId size="sm" iconOnly? />`:
    - Hidden when `!enabled`.
    - Disabled, with `title` set to the reason, when `!configured` (`SW.whatsapp.hakunaNamba`) or `!connected` (`SW.whatsapp.haijaunganishwa`).
    - On click: build, send, then `toast.success(SW.whatsapp.imetumwa)`, or `toast.error(resolveApiErrorMessage(err))`. A 504 shows `SW.whatsapp.haijathibitishwa`.
    - Shows a spinner while sending and is disabled during the send.
    - Icon: lucide `MessageCircle`.
- Placement (every spot that has a PDF button today):
  - ReportsPage main export, next to PDF/Excel.
  - ReportsPage closing-row exports (`handleClosingExport`), with `reportType="closing"` and `branchId={closing.branch_id}`.
  - ClosingPage row exports (around `ClosingPage.jsx:190`) and the "closed today" export (around `:289`).
- Translations:
  - Section `whatsapp: { tuma, imetumwa, haijaunganishwa, hakunaNamba, haijathibitishwa, ... }` (Swahili copy: "Tuma WhatsApp", "Imetumwa WhatsApp ✓", "WhatsApp haijaunganishwa", "Namba ya kupokea haijawekwa", "Haijathibitishwa — angalia WhatsApp kabla ya kutuma tena").
  - `makosa.msimbo` entries for every Task 3 code and `INVALID_PHONE`, `WHATSAPP_RECEIVER_LOCKED`.
  - English equivalents in `en.js`.

- [ ] **Step 1: Implement** the refactor, service, hook, component, placements and translations.
- [ ] **Step 2: Build.** `cd frontend && node node_modules/.bin/vite build`. Expected: build succeeds with no new warnings about missing imports.
- [ ] **Step 3: Check in the browser** with the backend running, `WHATSAPP_ENABLED=true`, and the local gateway either linked or stopped:
  - With the gateway stopped, the button is disabled and shows the "haijaunganishwa" tooltip.
  - With it linked, a sales report and a closing each arrive on the receiver phone, and the success toast shows.
  - Sending the same report again within 10 minutes shows the duplicate message.
  - The PDF download still produces an identical file.
  - With `WHATSAPP_ENABLED=false`, the button is hidden.
- [ ] **Step 4: Commit** — `feat(whatsapp): Tuma WhatsApp button on reports and closings`.

### Task 5: Frontend — receiver settings card (admin/super_admin)

**Files:**
- Create: `frontend/src/features/branches/WhatsAppSettingsCard.jsx`
- Modify: `frontend/src/features/branches/BranchesPage.jsx` (render the card; the page is already gated by `branches.manage` = admin/super_admin)
- Modify: translations (`whatsapp.mipangilio`, `whatsapp.nambaYaKupokea`, `whatsapp.imefungwaNaSeva`, `whatsapp.imeunganishwa`, …)

**Interfaces:**
- Consumes: `whatsappService.getSettings/updateSettings`.
- Produces: a card showing:
  - The receiver number (input plus a Save button; read-only with a note `SW.whatsapp.imefungwaNaSeva` when `locked`).
  - The connection badge (green "Imeunganishwa" / red "Haijaunganishwa").
  - A hint that the number is entered as `07XX XXX XXX`.
  - The card isn't rendered when `enabled` is false.

- [ ] **Step 1: Implement** the card and its placement.
- [ ] **Step 2: Build.** `node node_modules/.bin/vite build`. Expected: success.
- [ ] **Step 3: Check in the browser:**
  - As admin: save `0712 345 678`, and it shows back as `255712345678`. Junk shows the `INVALID_PHONE` message.
  - With `WHATSAPP_RECEIVER_OVERRIDE` set, the field is read-only with the note.
  - As cashier: no access to `/matawi`.
- [ ] **Step 4: Commit** — `feat(whatsapp): receiver number settings card`.

### Task 6: Docs, then production and demo rollout over SSH

**Files:**
- Modify: `RUNBOOK.md` (section "WhatsApp gateway (OpenWA)"), `DEPLOYMENT.md` (Docker + OpenWA component, ports, env vars)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the docs.**
  - RUNBOOK covers:
    - Status check (`docker ps`, `curl -H "X-API-Key: …" 127.0.0.1:2785/api/sessions/<id>`).
    - Re-linking by QR over the SSH tunnel `ssh -L 2785:127.0.0.1:2785 dukani-prod`.
    - Rotating the sender SIM (new session, update `OPENWA_SESSION_ID`, restart both backends).
    - Keeping the sender phone active (open WhatsApp every ~2 weeks).
    - The daily caps.
  - DEPLOYMENT adds OpenWA to the architecture diagram/list and the new backend env vars. Commit: `docs: WhatsApp gateway runbook and deployment notes`.
- [ ] **Step 2: Get the user's go-ahead, then push to `main`.** This auto-deploys prod and demo, and the Alembic migration runs with the deploy. Both backends still have `WHATSAPP_ENABLED` unset (false), so nothing user-visible changes. Verify both `/health` endpoints are healthy, and `alembic current` on both shows the new head.
- [ ] **Step 3: Install Docker on `dukani-prod`.** Check the OS (`cat /etc/os-release`), install Docker Engine from Docker's official apt repo, and `sudo usermod -aG docker cctvpoint` if needed. Expected: `docker info` works.
- [ ] **Step 4: Start OpenWA on the server.**
  - Copy `deploy/openwa/docker-compose.yml` to `/opt/openwa/`.
  - Create `/opt/openwa/.env` (mode 600) with `OPENWA_API_KEY=$(openssl rand -hex 32)` and no Swagger.
  - `docker compose up -d`.
  - Create the session via `POST /api/sessions {"name":"dukani-reports"}` and start it. Record its id.
  - Expected: `curl 127.0.0.1:2785/...` works locally, and port 2785 is not reachable from outside (check `ss -ltn` shows `127.0.0.1:2785`).
- [ ] **Step 5: PAUSE for the user to link the phone.**
  - The user runs `ssh -L 2785:127.0.0.1:2785 dukani-prod` and opens the dashboard/QR at `http://127.0.0.1:2785`, or Claude fetches `GET /api/sessions/{id}/qr` and renders the QR in the terminal.
  - The user scans it from the sender phone's WhatsApp → Linked devices.
  - Expected: session status `ready`.
- [ ] **Step 6: Configure both backends.**
  - **Prod** (`/opt/dukanipos/backend/.env`): `WHATSAPP_ENABLED=true`, `OPENWA_API_KEY`, `OPENWA_SESSION_ID`, plus defaults.
  - **Demo** (`/opt/dukanipos-demo/backend/.env`): the same gateway values, plus `WHATSAPP_DAILY_CAP=15`, `WHATSAPP_CAPTION_PREFIX="[DEMO] "`, `WHATSAPP_RECEIVER_OVERRIDE=<receiver>`.
  - Restart `dukani-pos` and `dukani-pos-demo`.
  - Expected: `/whatsapp/status` shows `connected: true` on both (call it with an admin token).
- [ ] **Step 7: Set the receiver and test.**
  - Set the receiver number in prod via the settings card (ask the user for it).
  - Send one real closing from prod and one from demo.
  - Expected: both PDFs arrive, the demo one captioned `[DEMO]`, and both are audit-logged.
- [ ] **Step 8: Hand back to the user.** Report what's live, the session id location, and the reminder about keeping the sender phone active.
