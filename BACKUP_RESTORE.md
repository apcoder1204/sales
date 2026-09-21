# Backup and restore

## What's backed up, and when

Production (`dukani_pos`) is backed up twice, independently, so a quiet
week with no deploys still gets fresh backups:

| Trigger | Script | Where | Retention |
|---|---|---|---|
| Every deploy (any push to `main`) | inline in `deploy.sh` | `/home/cctvpoint/backups/pre_deploy_<timestamp>.sql` | none enforced — manual cleanup |
| Nightly, 02:00 UTC, regardless of deploy activity | `backend/scripts/backup_production_db.sh` (cron) | `/home/cctvpoint/backups/nightly_<timestamp>.sql.gz` | 14 days, auto-pruned by the script itself |

The demo database (`dukani_pos_demo`) is **not** backed up — it's reset to
fresh seed data every night at 03:00 UTC
(`backend/scripts/reset_demo_data.sh`), so nothing in it is meant to
persist.

Both backup paths run on the production server itself — **there is
currently no off-server copy**. If the server/disk is lost, every backup
is lost with it. This is a real, known gap (see [Known
gaps](#known-gaps)).

## Verifying a backup is good

`backup_production_db.sh` already does one automatic check: it refuses to
prune old backups if the dump it just took is suspiciously small (under
1000 bytes), since a truncated/empty dump is worse than no backup — it's a
false sense of safety.

Structural validation performed this session on a real backup file
(`pre_deploy_20260921_180035.sql`): a well-formed `pg_dump` file has a
matching `\restrict`/`\unrestrict` pair (Postgres 18's dump-integrity
wrapper — if the file were truncated, the closing marker would be missing
or wouldn't match), one `CREATE TABLE` and one `COPY` per real table (18 of
each, matching this schema), and the standard "dump complete" footer. That
file passed. This confirms the dump isn't corrupted or cut short —
it does **not** confirm the data restores cleanly into a working database.

**A true restore test (into a scratch database) was not performed as part
of this pass.** The `dukani` Postgres role does not have `CREATEDB`
privilege, so creating a throwaway database to restore into requires
Postgres-superuser access (interactive `sudo`, which isn't available
non-interactively). Doing this once — really restoring a real backup into
a scratch DB and confirming the app can read from it — is the single
highest-value remaining step here and should be done by whoever has that
access, ideally on a recurring schedule (monthly is reasonable), not just
once.

## Restore procedure

**This is destructive to whatever the target database currently contains.
Never run the restore step against `dukani_pos` unless you have already
confirmed (via a scratch-database test, or because production is already
lost) that this is really what you want.**

1. Pick the backup to restore from `/home/cctvpoint/backups/` — nightly
   backups are `.sql.gz` (gzipped), pre-deploy ones are plain `.sql`.
2. Create (or clear) the target database:
   ```bash
   # For a scratch/test restore (safe) — as a Postgres superuser:
   createdb -h localhost -U postgres dukani_pos_restore_test

   # For a real disaster-recovery restore (destructive — only once you're sure):
   # drop and recreate dukani_pos itself, or restore into a new DB and
   # repoint DATABASE_URL at it — dropping the live DB is a one-way door.
   ```
3. Restore:
   ```bash
   # gzipped nightly backup:
   gunzip -c /home/cctvpoint/backups/nightly_<timestamp>.sql.gz | \
     psql -h localhost -U dukani -d <target_db>

   # plain pre-deploy backup:
   psql -h localhost -U dukani -d <target_db> < /home/cctvpoint/backups/pre_deploy_<timestamp>.sql
   ```
4. Verify: `psql -d <target_db> -c "SELECT count(*) FROM sales;"` (or any
   table you expect to have rows) and spot-check a few real records — row
   counts alone can hide a partially-corrupt restore.
5. Only for a real disaster recovery: update `DATABASE_URL` in
   `/opt/dukanipos/backend/.env` if you restored into a differently-named
   database, then `sudo systemctl restart dukani-pos` and confirm
   `curl -sf http://127.0.0.1/health` reports `"database": {"status": "ok"}`.

## Known gaps

- **No off-server copy.** Losing the server loses every backup with it.
  The cheapest fix is a cron step appended to `backup_production_db.sh`
  that `scp`/`rclone`s the fresh dump to a second machine or object
  storage right after it's written — deliberately not done here since it
  needs credentials/a destination this pass doesn't have access to
  provision.
- **No recurring restore test.** See above — needs Postgres-superuser
  access to set up `CREATEDB` for a dedicated backup-verification role, or
  to be run manually by whoever has postgres superuser access.
- **No retention on `pre_deploy_*.sql` backups** — only the nightly ones
  self-prune. On an actively-deployed server these will accumulate
  indefinitely. Low priority (each is under 200KB in practice) but worth
  folding into the same script eventually.
