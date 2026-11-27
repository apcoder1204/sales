# Production runbook

Operational playbook for `pos.cctvpoint.org` / `demo.cctvpoint.org`. See
`DEPLOYMENT.md` for the architecture these procedures assume, and
`BACKUP_RESTORE.md` for anything data-recovery related.

## First checks, always

```bash
ssh dukani-prod
curl -s http://127.0.0.1/health | python3 -m json.tool     # prod, via nginx
curl -s -H 'Host: demo.cctvpoint.org' http://127.0.0.1/health | python3 -m json.tool
sudo -n systemctl status dukani-pos dukani-pos-demo cloudflared
tail -50 /home/cctvpoint/deploy.log
```

`/health` returns `"status": "unhealthy"` (HTTP 503) specifically when the
database is unreachable — that's the single most useful signal for
distinguishing "the app process is fine but something downstream broke"
from "the whole process is down."

## Incident: site is down / users can't log in

1. Check `/health` first (above) — if it's 503 with `database.status:
   "unreachable"`, this is a Postgres problem, not an app problem. Check
   `sudo -n systemctl status postgresql` and disk space (`df -h`) before
   anything else.
2. If `/health` itself doesn't respond at all: `sudo -n systemctl status
   dukani-pos`. If it's not `active (running)`:
   `sudo -n systemctl restart dukani-pos`, wait a few seconds, recheck.
3. If the service is `active` but requests still fail, check application
   logs: `sudo journalctl -u dukani-pos -n 100 --no-pager`.
4. **Known historical incident — webhook silently stopped restarting the
   backend.** `dukani-deploy-webhook.service` once had
   `NoNewPrivileges=true` set, which silently blocked the `sudo systemctl
   restart dukani-pos` step inside `deploy.sh` from ever taking effect —
   deploys appeared to succeed (the script kept running, git pulled fine)
   but the *running* process was never actually replaced, for about two
   days, undetected, because the old `/health` (pre this hardening pass)
   only proved the stale process was still alive. If a deploy "succeeds"
   in the log but the app's behavior doesn't match what was just pushed:
   check `systemctl show dukani-pos -p ActiveEnterTimestamp` against the
   time of the most recent entry in `deploy.log` — if the service's uptime
   predates the "latest" deploy, this is happening again. Check
   `dukani-deploy-webhook.service`'s unit file for `NoNewPrivileges` or
   any other directive that could block its `sudo -n systemctl restart`
   calls.
5. **Known historical incident — login fails in the browser but curl
   works fine.** If curl-based API testing looks completely healthy but
   real browser logins fail, check the browser's DevTools Network/Console
   tab directly rather than trusting server-side checks — this exact
   gap once let a stale `frontend/.env.production` (baking
   `VITE_API_BASE_URL=http://localhost:8000` into the built bundle) go
   undetected for as long as verification only used curl, which calls the
   API by real hostname directly and never exercises the frontend JS at
   all. If you see `ERR_CONNECTION_REFUSED` to `localhost:8000` in a
   user's console, the deployed frontend bundle was built without (or
   with a stale) `.env.production`/`.env` — rebuild
   (`cd /home/cctvpoint/dukani-src/frontend && npm run build`) and re-sync
   to `/opt/dukanipos/frontend/dist/`.

## Incident: a deploy needs to be rolled back

There is no one-command rollback — `deploy.sh` always deploys whatever
`origin/main` currently points to. To roll back:

```bash
# On your own machine, not the server:
git log --oneline -10             # find the last-known-good commit
git revert <bad-commit>..HEAD     # or git reset --hard <good-commit> if you're
                                   # certain nothing after it should survive
git push origin main              # this triggers a normal deploy of the reverted state
```

If the bad commit included a migration that needs to come back too, a
`git revert` alone won't undo the migration — you'll need a new
down-migration or a manual `alembic downgrade`, and you should back up
first regardless (`BACKUP_RESTORE.md`).

## Incident: a migration failed mid-deploy

`deploy.sh` has `set -e` — if `alembic upgrade head` fails, the script
stops there. The rsync into `/opt/dukanipos/backend` already happened
(code is new), but the running process hasn't been restarted yet (still
old code, now against a possibly-partially-migrated database — check
`alembic current` vs `alembic heads` to see exactly where it stopped).
Fix the migration issue, then re-run `/home/cctvpoint/deploy.sh` manually
(safe — `git reset --hard` and the whole pipeline are idempotent) rather
than trying to resume by hand.

## Running the release validation gate manually

```bash
cd ~/POSsystem   # your local checkout, not the server
./deploy/validate_release.sh
```

Checks: no secret-shaped files tracked by git (current tree + full
history), backend compiles + full test suite passes, exactly one alembic
head, frontend builds clean, en/sw translation parity. Exit code 0 = safe
to push to `main`. This is **not** currently wired into the deploy
pipeline itself as a hard gate (see `DEPLOYMENT.md`'s Known gaps) — run it
yourself before pushing.

## Checking backups

```bash
ls -la /home/cctvpoint/backups/ | tail -20
tail -20 /home/cctvpoint/backup.log      # nightly cron output
crontab -l                                # confirm both cron jobs are present
```

Full restore procedure: `BACKUP_RESTORE.md`.

## Demo environment

Resets to fresh seed data nightly at 03:00 UTC
(`/opt/dukanipos-demo/backend/scripts/reset_demo_data.sh`, logged to
`/home/cctvpoint/demo-reset.log`). If demo looks stale or broken:

```bash
tail -30 /home/cctvpoint/demo-reset.log
sudo -n systemctl status dukani-pos-demo
# force an immediate reset:
/opt/dukanipos-demo/backend/scripts/reset_demo_data.sh
```

The reset script refuses to run at all unless
`/opt/dukanipos-demo/backend/.env` actually points at `dukani_pos_demo` —
if you ever see it exit immediately with "REFUSING TO RUN", something
about the demo `.env` was changed; do not bypass that check, fix the
`.env` instead.

## WhatsApp gateway (OpenWA)

Reports are sent as PDFs to one receiver number through OpenWA, a
self-hosted, **unofficial** WhatsApp client running in Docker at
`127.0.0.1:2785` (compose file: `/home/cctvpoint/openwa/docker-compose.yml`, secrets in
`/home/cctvpoint/openwa/.env`, mode 600). The sender is a dedicated spare SIM, not the
business number: WhatsApp may restrict it, the receiver is never at risk.

**Is it connected?** The Matawi page's "WhatsApp — Ripoti" card shows a
green/red badge. From the server:

```bash
docker ps --filter name=openwa-api
KEY=$(grep OPENWA_API_KEY /home/cctvpoint/openwa/.env | cut -d= -f2)
SID=$(cat /home/cctvpoint/openwa/session_id)
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:2785/api/sessions/$SID | python3 -m json.tool   # "status": "ready"
```

**Badge red / "WhatsApp haijaunganishwa"**

1. Container down → `cd /home/cctvpoint/openwa && docker compose up -d`.
2. Session not `ready` → try `POST /api/sessions/$SID/start` (same headers).
3. Still `qr_ready` / logged out → re-link with a pairing code. On the sender
   phone open WhatsApp → Settings → Linked devices → Link a device → "Link
   with phone number instead" and keep that screen open, *then* request the
   code (it is only valid ~3 minutes; an expired code makes the phone say
   "couldn't link device"):
   ```bash
   curl -s -X POST -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
     -d '{"phoneNumber":"255656653665"}' http://127.0.0.1:2785/api/sessions/$SID/pairing-code
   ```
   Fallback: QR via the dashboard over `ssh -L 2785:127.0.0.1:2785 dukani-prod`
   (`http://127.0.0.1:2785`, log in with the API key).

**Upgrading / re-pulling the image.** This server downloads from GitHub's
container registry (ghcr.io) at ~46 KB/s, so `docker compose pull` stalls on
the ~576 MB image. Pull the same image from Docker Hub instead and retag it:
`docker pull rmyndharis/openwa:<tag>`, compare its digest with the ghcr one,
`docker tag rmyndharis/openwa:<tag> ghcr.io/rmyndharis/openwa:<tag>`, update
the tag in `docker-compose.yml`, then `docker compose up -d --pull never`.

**Keep the sender phone alive.** WhatsApp logs out linked devices if the
phone itself is unused for ~14 days: open WhatsApp on it at least every
couple of weeks and keep it charged and on the network.

**Sender number got restricted / replaced.** Put WhatsApp on a new SIM,
create a new session (`POST /api/sessions {"name": "dukani-reports-2"}`, then
`/start`), link it as above, set the new id as `OPENWA_SESSION_ID` in both
`/opt/dukanipos/backend/.env` and `/opt/dukanipos-demo/backend/.env`, then
`sudo -n systemctl restart dukani-pos dukani-pos-demo`.

**Limits.** Sends are capped per business day (`WHATSAPP_DAILY_CAP`: prod 50,
demo 15, counted separately) and the same report is refused if re-sent within
10 minutes. Every send attempt is in the audit log (`WHATSAPP_REPORT_SEND`,
category System) with the sender, report, PDF SHA-256 and outcome.

**Turn it off quickly.** Set `WHATSAPP_ENABLED=false` in the backend `.env`
and restart the service: the button and settings card disappear.

## Customers and debts (Wateja na Madeni)

**Who can do what.** A cashier can register customers, sell on credit at their own
branch (only to an active customer, within the customer's credit limit), and
receive debt payments at their own branch. A cashier can also enter an old
debt for their own branch. Only the admin can set or raise a credit limit,
deactivate a customer, reverse a debt payment, or approve, reject and cancel
old debts. A general manager can look but not change anything.
Every one of these is in the audit log (category "sales").

**Raising a credit limit.** Wateja → customer → "Mkopo". A reason is required;
the audit entry keeps the old and new limit and what the customer owed at that
moment. The limit is one total across all branches. A credit limit of 0 means
"no credit".

**A debt payment was recorded wrongly** (wrong amount, wrong customer, or the
wrong branch). Don't edit anything. An admin opens the customer → Malipo →
"Batilisha" on that payment, gives a reason, then records the correct payment.
The original stays visible as reversed. A payment can't be reversed once that
branch's day is closed: reopen the day first (admin), reverse, re-record, close.
Payments taken at the till during a sale are undone only by voiding the sale.
A sale with debt payments against it can't be voided until those are reversed.

**Seeing who owes.** Madeni → Madeni Yote lists every open debt (credit sales
and approved old debts) with totals, filters and a "Pokea Malipo" button per
row. A cashier sees only their own branch.

**Old debts (Madeni ya Zamani).** The admin, or a cashier for their own branch,
enters the debt with a reference (e.g. ledger book page). It waits as
"Linasubiri" and is not owed yet. The admin checks it against the notebook and
presses "Idhinisha" (or "Kataa" with a reason) as a separate step; each
business has one admin, so the admin may approve their own entries. An
approved old debt that was wrong: the admin presses "Batilisha" with a reason.
That only works while no active payment is recorded on it; reverse such
payments first. The cancelled entry stays visible with who cancelled it and
why, and the ledger gets an offsetting "opening_void" credit.

**Statements, ageing and reports.**
- **Statement:** Wateja → customer → "Taarifa". Pick a date range and download it as PDF or Excel, or send it to WhatsApp. The closing balance always equals the ledger balance up to the end date; a different figure means a bug, not a data fix.
- **Debt dashboard and ageing:** at the top of Madeni → Madeni Yote, with the "Umri wa Madeni" tab next to the list. Days overdue are counted from each debt's due date, using Tanzania business dates.
- **Debt reports:** Ripoti → the seven "Madeni: …" types. Credit-limit use is for the admin and manager only.
- **Who sees what:** a cashier sees only their branch everywhere. The admin and manager see all branches or the one picked in the switcher.

**Follow-up notes don't change balances.** "Ufuatiliaji" on the customer page records calls, visits and promises to pay. The cashier writes for their own branch and the admin for any POS branch; the manager can only read. Nothing there touches payments or what is owed.

**Reconciliation (Upatanisho wa Hesabu).** Madeni → Upatanisho wa Hesabu, for the admin and the manager. Pick a scope (all branches, one branch or one customer) and a period, then press "Anzisha Upatanisho". The run checks that sales, till payments, debt payments, the customer ledger, P&L and the stored daily closing totals all agree. Debts and payments are always checked in full; the period applies only to sales, P&L and closings.
- **Imepita:** everything agrees. **Onyo:** only warnings: a mobile-money or bank reference used on more than one payment, or an older sale whose stored payment method doesn't match its payment. **Imeshindwa:** at least one money difference.
- **A run never changes money.** It only writes its own result and the list of differences. Never "fix" a figure by editing the database.
- **Handling a difference.** Each one says in plain words what is wrong and which record. Fix it with the normal action: reverse a wrong payment; void a wrong sale; for a closing total that doesn't match, reopen that day and close it again (it recomputes from the payments). Then press "Badilisha Hali" → "Imetatuliwa" with a reason and a supporting reference (e.g. the reversal's payment number). The system refuses "Imetatuliwa" while the difference is still there.
- **A difference that is accepted as it is** (e.g. a known historical case): "Imepuuzwa", with a reason and a reference. A later run stays quiet about it unless the amount changes.
- "Inakaguliwa" marks one you are looking into. "Imetatuliwa" and "Imepuuzwa" are final; a new run raises a fresh entry if the problem comes back.
- "Kagua Tena" on a row re-checks just the affected sale, payment, customer or branch.
- The exceptions also appear as a report: Ripoti → "Madeni: Tofauti za Upatanisho" (PDF, Excel, WhatsApp).
- On a healthy system every run passes; a failure means something went wrong in the data or the code and is worth investigating, not just dismissing.

**The customer ledger is append-only.** `customer_ledger_entries` has a database
trigger that refuses UPDATE and DELETE. Nobody should ever need to bypass it on
prod. The only sanctioned bypass is inside a single transaction:
`SET LOCAL dukani.ledger_maintenance = 'on'`. The demo reset and the tests use
it to wipe their own data. Never run it against production data; corrections
are always new rows (reversals), never edits.

**Where the money is counted.** Daily closing and the "by payment method"
figures come from the `payments` table: money actually received. The credit
part of a sale shows separately as "Mkopo Uliotolewa" and debt collections
as "Madeni Yaliyolipwa". Profit & loss still counts a sale's full value on
the day of the sale, and a later debt payment never adds revenue.

## Useful one-liners

```bash
# Deployed commit currently live:
cd /opt/dukanipos/backend && git -C /home/cctvpoint/dukani-src rev-parse --short HEAD

# Tail live backend logs:
sudo journalctl -u dukani-pos -f

# Confirm which alembic revision each database is actually on:
cd /opt/dukanipos/backend && .venv/bin/alembic current
cd /opt/dukanipos-demo/backend && .venv/bin/alembic current

# Nginx config test before reloading after an edit:
sudo nginx -t && sudo systemctl reload nginx
```
