# Deploying DUKANI POS

This describes the **actual, currently-running** production and demo
deployment — not a hypothetical target. If you're setting up a brand-new
server from scratch, see [New server bootstrap](#new-server-bootstrap) at
the end; everything above that describes the live system at
`pos.cctvpoint.org` and `demo.cctvpoint.org`.

## Architecture

```
Internet
   │
   ▼
Cloudflare Tunnel (cloudflared.service)
   │  no inbound ports open on the server at all — outbound-only tunnel
   ▼
Nginx :80 (routes by server_name)
   │
   ├── pos.cctvpoint.org   ──┬── /            → static files: /opt/dukanipos/frontend/dist
   │                         ├── /api/        → proxy: 127.0.0.1:8000
   │                         ├── /health      → proxy: 127.0.0.1:8000/health
   │                         └── /deploy-webhook → proxy: 127.0.0.1:9001
   │
   └── demo.cctvpoint.org  ──┬── /            → static files: /opt/dukanipos-demo/frontend/dist
                             ├── /api/        → proxy: 127.0.0.1:8001
                             └── /health      → proxy: 127.0.0.1:8001/health

systemd services (all run as user `cctvpoint`):
  dukani-pos             gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8000
                          WorkingDirectory=/opt/dukanipos/backend
  dukani-pos-demo        same, -b 127.0.0.1:8001, WorkingDirectory=/opt/dukanipos-demo/backend
  dukani-deploy-webhook  python3 /home/cctvpoint/webhook_receiver.py  (listens on :9001)
  cloudflared            Cloudflare Tunnel client
```

Two independent Postgres databases on the same server: `dukani_pos` (prod,
role `dukani`) and `dukani_pos_demo` (demo, role `dukani_demo`).

There is **no Docker** in this deployment and no load balancer beyond
Nginx — this is a single-server setup. (An earlier draft of this doc
described a Docker Compose + certbot setup; that was never actually built
out — this document now matches what's really running.)

## How a deploy actually happens

Every push to `main` on GitHub triggers a deploy automatically — there is
no separate CI step and no manual "click to deploy":

1. GitHub sends a `push` webhook to `https://pos.cctvpoint.org/deploy-webhook`.
2. Nginx proxies it to `webhook_receiver.py` on `127.0.0.1:9001`, which verifies
   the `X-Hub-Signature-256` HMAC signature (timing-safe comparison) against
   `WEBHOOK_SECRET` before doing anything else. An invalid signature is
   logged and rejected with 401; nothing runs.
3. On a verified `push` to `refs/heads/main`, it runs
   `/home/cctvpoint/deploy.sh` in the background and returns immediately.
4. `deploy.sh` (source lives in this repo isn't committed — it's
   server-local; see [Server-local files](#server-local-files-not-in-this-repo)):
   - `git fetch` + `git reset --hard origin/main` in `/home/cctvpoint/dukani-src`
   - `pg_dump`s the **production** database to `/home/cctvpoint/backups/pre_deploy_<timestamp>.sql`
     (on top of the independent nightly backup — see `BACKUP_RESTORE.md`)
   - rsyncs `backend/` into `/opt/dukanipos/backend/` (excluding `.venv`,
     `__pycache__`, `.env`, `tests/`)
   - `pip install -r requirements.txt` and `alembic upgrade head` against
     the **production** database
   - builds the frontend once (`npm ci && npm run build`)
   - rsyncs `frontend/dist/` into `/opt/dukanipos/frontend/dist/`
   - `sudo systemctl restart dukani-pos`, then `curl -sf http://127.0.0.1/health`
   - if `/opt/dukanipos-demo/backend/.env` exists (i.e. demo has been
     bootstrapped), repeats the backend sync + migrate + restart for the
     **demo** database and service, reusing the same frontend build
     (same-origin API calls, so one build serves both)
   - all output appended to `/home/cctvpoint/deploy.log`

A deploy touches **both** prod and demo from a single push to `main` — there
is no separate demo branch or deploy trigger. If you need to test something
against demo only before it reaches production, do that locally or in a
throwaway branch and merge to `main` when ready.

**Before every push to `main`**, run `./deploy/validate_release.sh` locally
— it will not stop a bad push from deploying (no CI gate exists yet — see
[Known gaps](#known-gaps) below), but it catches the two classes of mistake
that have actually happened in this project: a tracked secret file, and a
broken test suite/build going out unnoticed.

## Manual deploy (if the webhook is down or you need to force a redeploy)

```bash
ssh dukani-prod   # alias for cctvpoint@100.90.50.20, see SSH access below
/home/cctvpoint/deploy.sh
tail -f /home/cctvpoint/deploy.log   # watch it run
```

## SSH access

- Key: `~/.ssh/dukani_demo_deploy`
- Host alias `dukani-prod` in `~/.ssh/config` → `cctvpoint@100.90.50.20`
- `cctvpoint` has full `sudo` (password-gated) plus passwordless `sudo` for
  a narrow, explicit set of commands only:
  `systemctl {restart,status,is-active} dukani-pos`,
  `systemctl {restart,status,is-active,start,stop} dukani-pos-demo`.
  Anything else needs the interactive sudo password — this is deliberate,
  not a bug, if a non-interactive session (e.g. this deploy pipeline, or an
  AI agent working over SSH) can't run a broader sudo command.

## Environment variables

`backend/.env` (production) and the demo equivalent are **not** in this
repo (gitignored) and are never printed in full by any script — only key
*names* are safe to log. Reference (see `backend/app/config.py` for exact
types/defaults):

| Variable | Notes |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` — different DB name per environment (`dukani_pos` vs `dukani_pos_demo`) |
| `SECRET_KEY` | JWT signing key — different value per environment, never reused |
| `CORS_ORIGINS` | JSON array, the exact origin(s) only — never `["*"]` in production |
| `ENABLE_HSTS` | must be `true` on both prod and demo (both are HTTPS-only via the Cloudflare Tunnel) |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | password-reset email; prod only in practice |
| `FRONTEND_URL` | used to build the password-reset link sent by email |
| `DEFAULT_TIMEZONE` | `Africa/Dar_es_Salaam` — see the business-date/timezone notes in `SECURITY.md`/code comments; changing this changes what "today" means for every closing/report |
| `REDIS_URL` | present in the prod `.env` as a leftover from before Redis was removed from the app (rate limiting is in-process `memory://` now) — unused, safe to remove whenever the file is next touched, not urgent |

## Known gaps

- **No CI gate.** A push to `main` deploys unconditionally, even if
  `pytest` would fail. `validate_release.sh` exists precisely to be run
  *before* that push, but nothing currently enforces it. Wiring it into
  `deploy.sh` as a hard gate (abort + alert before touching
  `/opt/dukanipos` if validation fails) is the natural next step — not done
  here because changing the live deploy pipeline is exactly the kind of
  action that needs a deliberate, separate go-ahead, not a side effect of
  a documentation pass.
- **Frontend build failures aren't caught mid-deploy for the second
  (demo) sync** — the same build artifact is reused, so if it built once
  for prod it'll be there for demo too; this is a non-issue in practice
  since it's one build shared by both.

## New server bootstrap

If `pos.cctvpoint.org`/the whole server were lost and you needed to stand
up a replacement from scratch, this repo alone is not sufficient — you'd
also need: the latest backup (`BACKUP_RESTORE.md`), a fresh `WEBHOOK_SECRET`
+ GitHub webhook re-registration, fresh `SECRET_KEY`/`RESEND_API_KEY`/DB
credentials, the Cloudflare Tunnel re-authenticated to the domain, and
`webhook_receiver.py`/`deploy.sh` re-created from the descriptions above
(they're server-local, not in git). This is a real single-point-of-failure
gap — there is currently no infrastructure-as-code (Terraform/Ansible/etc.)
that could rebuild the server unattended. Treat this section as a checklist
for a manual rebuild, not a script to run.

1. Fresh Ubuntu 22.04/24.04 host, Python 3.12, Node 20, PostgreSQL, Nginx,
   `cloudflared` installed and authenticated to the domain.
2. Create the `dukani`/`dukani_demo` Postgres roles + `dukani_pos`/
   `dukani_pos_demo` databases; restore from the latest backup
   (`BACKUP_RESTORE.md`) or run `alembic upgrade head` + `python -m app.db.seed`
   for a clean install.
3. Clone this repo to `/home/cctvpoint/dukani-src`; set up
   `/opt/dukanipos/backend` (+ `.venv`, `.env`) and
   `/opt/dukanipos/frontend/dist` (and the `-demo` equivalents) as
   described in the architecture section above.
4. Re-create `webhook_receiver.py` and `deploy.sh` (this document describes
   their exact behavior above) with a **new** `WEBHOOK_SECRET`, and
   register a new GitHub webhook pointed at `/deploy-webhook` with that
   secret.
5. Create the systemd unit files (`dukani-pos`, `dukani-pos-demo`,
   `dukani-deploy-webhook`) matching the `ExecStart`/`WorkingDirectory`/
   `User` values in the architecture section, plus the scoped NOPASSWD
   sudoers entries for the two service names.
6. Re-add both cron jobs (`backend/scripts/backup_production_db.sh` at
   02:00 UTC, `backend/scripts/reset_demo_data.sh` at 03:00 UTC — see
   `BACKUP_RESTORE.md`).
7. Nginx configs are the two server blocks shown in the architecture
   section — recreate them under `/etc/nginx/sites-available/`.
8. Immediately change every seeded default password (`1234`) before
   handing the system to real staff.
