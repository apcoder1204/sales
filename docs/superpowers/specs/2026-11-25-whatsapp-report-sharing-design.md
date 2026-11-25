# Send reports to WhatsApp — design

Date: 2026-11-25 · Status: approved 2026-11-25

## Intent

When someone is looking at a report in DUKANI POS (any report type on the
Ripoti page, or a day closing on the Ufungaji page), they can press one
button and the same PDF they could download is delivered to **one
designated WhatsApp number**: the person who reads all reports for the
business. No typing a number, no phone in hand.

## Goals

- A "Tuma WhatsApp" button next to the existing PDF/Excel buttons on:
  - `ReportsPage.jsx`: the main report export (all 9 report types) and the
    per-closing-row exports in the closing report list.
  - `ClosingPage.jsx`: the per-row closing exports and the "closed today"
    export.
- The real PDF is delivered (as a WhatsApp document), with a short Swahili
  caption: report title, branch (where applicable), period/date, and who sent
  it.
- One designated receiver number for the whole business, editable in the app
  by admin/super_admin.
- Clear feedback: success toast, or a specific error (gateway not connected,
  no number configured, send failed). Download keeps working regardless.
- Every send is written to the audit log.

## Non-goals

- Multiple receivers, per-branch receivers, or per-report routing.
- Scheduled / automatic sending (e.g. closing auto-sent at end of day).
- Receiving or replying to WhatsApp messages; no webhooks from OpenWA.
- Linking the sender phone (QR scan) from inside DUKANI POS — done once in
  OpenWA's own dashboard.
- Sending Excel files.

## Anti-goals

- The OpenWA API key must never reach the browser.
- A user must not be able to send to an arbitrary number — the receiver is
  only ever the configured one, read server-side.
- A user must not be able to send a report *type* they could not view: the
  server re-checks the caller's role against the same role gate as the
  matching `GET /reports/*` endpoint. **Builder's-call note (accepted
  risk):** because PDFs are built in the browser, the server cannot prove
  the uploaded PDF's *content* matches a report the user viewed. This is
  accepted: the receiver is the owner, the caption names the real sender and
  their branch (both taken server-side, never from the client), and the audit
  entry stores a SHA-256 of the PDF so any document can be traced to who
  sent it.
- Demo visitors must not be able to send to an arbitrary number or burn
  through the sender SIM's volume (see Demo site below).
- A WhatsApp/OpenWA outage must not break reports, downloads, or anything
  else in the app.

## Constraints

- **Gateway:** [OpenWA](https://github.com/rmyndharis/OpenWA) (MIT, self-hosted,
  unofficial WhatsApp client). It carries a non-zero risk of the **sender**
  number being restricted by WhatsApp; the receiver is not at risk. The
  sender is a dedicated spare SIM, never the business's main number.
- **Production has no Docker today.** Per `DEPLOYMENT.md`, prod and demo run
  as systemd services (`dukani-pos`, `dukani-pos-demo`) behind nginx +
  Cloudflare Tunnel. Docker Engine must be installed on the server to run
  OpenWA as a container.
- PDFs are generated **in the browser** with jsPDF (`downloadPDF` in
  `frontend/src/utils/reportExport.js`, built from the shared
  `normalise(type, data, period)`). There is no server-side PDF generation and
  this design does not add one.
- `httpx` is currently only in `requirements-dev.txt`; it must move to
  `requirements.txt` for the backend to call OpenWA.
- Existing conventions apply: datetimes written to `TIMESTAMP` columns use
  `.replace(tzinfo=None)`; avoid enum-alter migrations; Swahili UI strings
  live in the `SW` constants.

## Approaches considered

1. **Click-to-chat link (`wa.me/<number>?text=…`)** — opens WhatsApp with
   the report as pre-typed text; user taps Send. Zero risk, no server
   component, but text only (no PDF) and needs the user's own WhatsApp.
2. **Web Share API with the PDF file** — real PDF via the phone's share
   sheet, but the user must pick the contact (designated number is lost) and
   desktop support is unreliable.
3. **Self-hosted OpenWA gateway (chosen)** — real PDF, fully automatic, to a
   fixed number. Trade-offs: sender-number ban risk, a new service to run
   (Docker), and the sender session can disconnect and need a QR re-scan.

Chosen by the user: **3, OpenWA**, with a dedicated sender SIM.

## Decided by the user

- Use OpenWA, hosted as a container on the server.
- Two numbers: a dedicated sender SIM linked to OpenWA, and one receiver
  (the person who reads all reports).
- One receiver for all reports from all branches.
- Scope includes **server setup**: Claude performs the prod steps on
  `dukani-prod` over SSH (install Docker, start OpenWA, set backend `.env`
  values for both prod and demo, restart `dukani-pos` and `dukani-pos-demo`), pausing only for the user to scan the QR
  code with the sender phone. Code ships first with `WHATSAPP_ENABLED=false`;
  it is switched on only after the session is linked and a test send works.

## Design (proposals accepted in conversation)

### Deployment

- Install Docker Engine on the prod server. Add an OpenWA compose file to the
  repo (e.g. `deploy/openwa/docker-compose.yml`) using
  `ghcr.io/rmyndharis/openwa:latest` pinned to a specific tag/digest.
- Engine: **Baileys** (`ENGINE_TYPE`), ~30–80 MB RAM, no headless Chromium.
- Database: SQLite (OpenWA's default), persisted in a named volume mounted at
  `/app/data` — session credentials must survive restarts/redeploys.
- Port 2785 bound to **127.0.0.1 only**; not exposed through nginx or the
  Cloudflare tunnel. The dashboard is reached for the one-time QR scan via an
  SSH tunnel (`ssh -L 2785:127.0.0.1:2785 dukani-prod`).
- `API_MASTER_KEY` set explicitly from a secret; `SEND_PACING_ENABLED` on.
- One OpenWA session (e.g. name `dukani-reports`), linked by QR from the
  sender phone.
- **Demo site (user decision): demo uses the same setup to demonstrate the
  feature** — same OpenWA gateway and session (same sender SIM), same
  receiver number. Because demo logins are shared, demo is hardened:
  - `WHATSAPP_RECEIVER_OVERRIDE` env var: when set, the receiver is taken
    from it and the in-app number field is read-only (shows the number,
    cannot be changed). Demo sets it to the same receiver as prod; prod
    leaves it unset and uses the in-app setting.
  - Captions on demo are prefixed `[DEMO]` (config `WHATSAPP_CAPTION_PREFIX`)
    so the receiver can tell demo sends from real ones.
  - Demo gets a lower daily cap (`WHATSAPP_DAILY_CAP=15`). Prod and demo have
    separate databases, so caps are counted separately; worst case per day is
    prod cap + demo cap (65), still a modest volume for one sender.
- RUNBOOK gains a short section: check gateway status, re-link by QR, rotate
  the sender SIM, keep the sender phone active (opens WhatsApp at least every
  ~2 weeks, or linked devices get logged out).

### Backend

- **Config (`app/config.py`, env-driven):** `WHATSAPP_ENABLED: bool = False`,
  `OPENWA_BASE_URL` (e.g. `http://127.0.0.1:2785/api`), `OPENWA_API_KEY`,
  `OPENWA_SESSION_ID`, `OPENWA_TIMEOUT_SECONDS`.
- **Receiver number storage:** a new small key/value `app_settings` table
  (migration), first key `whatsapp_report_number`. Stored normalised as
  digits with country code (Tanzania: `255XXXXXXXXX`); the API accepts
  `0XXXXXXXXX`, `+255…`, `255…` and normalises/validates.
- **`whatsapp_service.py`:** wraps OpenWA via `httpx.AsyncClient`:
  - `get_status()` → `GET /sessions/{id}` → connected / not connected / disabled.
  - `send_document(phone, pdf_bytes, filename, caption)` →
    `POST /sessions/{id}/messages/send-document` with JSON
    `{chatId: "<digits>@c.us", base64, mimetype: "application/pdf", filename, caption}`,
    header `X-API-Key`. (Exact path to be confirmed against the OpenWA
    Swagger at `/api/docs` during build — inferred from the documented
    `send-text` / media DTO pattern.)
  - Maps failures to domain errors: disabled, not configured, gateway
    unreachable/timeout, session not ready, rejected.
- **Routes (new `app/api/v1/whatsapp.py`):**
  - `GET /whatsapp/settings` (admin/super_admin) → `{number, enabled, status}`.
  - `PUT /whatsapp/settings` (admin/super_admin) → set the receiver number;
    audit-logged.
  - `GET /whatsapp/status` (any user with a report/closing permission) →
    `{enabled, configured, connected}` so the UI can disable the button with
    a reason.
  - `POST /whatsapp/send-report` — multipart: `file` (PDF), `report_type`,
    `title`, `period_label`, optional `branch_id`. Server:
    1. Checks the caller's **role** is allowed for `report_type`. The backend
       has no permission strings (those live only in the frontend's
       `permissions.js`); it gates by `require_role`. Copy the role list from
       each matching `GET /reports/*` endpoint in `app/api/v1/reports.py`
       (and the closings list endpoint for `closing`) into one
       `report_type → roles` map. For branch-scoped roles (cashier,
       store_keeper) the caption's branch is the user's own, resolved with
       `resolve_read_branch_id` — never the client's `branch_id`.
    2. Validates the file is a PDF (`%PDF` magic, size cap e.g. 10 MB).
    3. Builds the caption server-side from validated fields + the caller's
       name (client text is length-limited and used only inside the caption).
    4. Sends to the configured number; writes an audit log entry
       (report type, title, sender user, PDF SHA-256, success/failure —
       not the PDF itself).
  - **Volume guard (protects the sender SIM; ban risk is about total volume,
    not per user):** a **business-wide daily cap** (config
    `WHATSAPP_DAILY_CAP`, default 50) counted from the DB — successful
    `whatsapp.send_report` audit entries for the current business date — so
    it is shared across gunicorn workers without Redis. Plus **duplicate
    suppression**: the same PDF SHA-256 sent successfully within the last 10
    minutes is refused with "Ripoti hii imeshatumwa" (stops double-clicks
    and repeat sends). The existing slowapi limiter (per-IP, in-process) may
    also be applied as a coarse extra guard, but the DB cap is the real one.
  - **Meaning of "Imetumwa" (sent):** OpenWA accepted the message (2xx from
    `send-document`). No delivery confirmation / read receipts, no webhooks.
    With `SEND_PACING_ENABLED`, the request may wait during pacing, so the
    HTTP timeout (`OPENWA_TIMEOUT_SECONDS`, default 30) must cover that; on
    timeout the UI says the result is unknown ("Haijathibitishwa — angalia
    WhatsApp kabla ya kutuma tena") rather than "failed".

### Frontend

- `reportExport.js`: refactor so PDF generation returns a `Blob` (new
  `buildPDF(type, data, period)` → `{blob, filename}`); `downloadPDF` calls it
  and saves. No change to PDF content.
- New `whatsappService.js` (`getStatus`, `getSettings`, `updateSettings`,
  `sendReport(blob, meta)`).
- A reusable `SendWhatsAppButton` component placed beside PDF/Excel on
  `ReportsPage` and `ClosingPage` (all locations listed under Goals). It
  fetches status once per page; when not usable it is disabled with a
  tooltip giving the reason ("WhatsApp haijaunganishwa", "Namba ya kupokea
  haijawekwa"). On click: build PDF → upload → toast "Imetumwa WhatsApp ✓"
  or the specific error.
- Hidden entirely when `WHATSAPP_ENABLED` is false (status says `enabled:
  false`). On demo it is enabled (see Demo site).
- Settings card shows the number read-only with a note when the server
  reports the receiver is locked by `WHATSAPP_RECEIVER_OVERRIDE`.
- Admin/super_admin settings card ("WhatsApp — Ripoti"): receiver number
  field, save, and the connection status indicator. Placement: the builder
  picks the most natural existing admin page (there is no general settings
  page today).
- New Swahili strings added to `SW`.

## Left to the builder

- Exact caption wording (Swahili, short).
- Where the settings card lives among existing admin pages.
- Exact OpenWA image tag to pin, and env var spelling for the Baileys engine
  (confirm from OpenWA docs).
- Whether `app_settings` gets a generic repository or a minimal one.
- Test coverage shape, following the existing `backend/tests/` harness; OpenWA
  is mocked in tests (no real sends).
