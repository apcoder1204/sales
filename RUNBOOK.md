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
