#!/bin/bash
# Independent nightly backup of the PRODUCTION database.
#
# Until now the only backup was a side effect of a deploy (pg_dump right
# before each `deploy.sh` run) — a quiet week with no code pushes meant no
# fresh backup at all. This runs on its own schedule regardless of deploy
# activity.
#
# Safety: the target database name is hardcoded below, never taken from an
# argument or from the process's own DATABASE_URL/.env — this script must
# never be able to run against the demo database by a copy-paste or
# fat-finger mistake. It refuses to run unless it can positively confirm
# the backend it's operating on is configured for the production database.
# Mirrors the same guardrail pattern as reset_demo_data.sh.
#
# Intended to run as a nightly cron job on the production instance only:
#   0 2 * * * /opt/dukanipos/backend/scripts/backup_production_db.sh >> /home/cctvpoint/backup.log 2>&1
set -euo pipefail

PROD_DB_NAME="dukani_pos"
BACKEND_DIR="/opt/dukanipos/backend"
BACKUP_DIR="/home/cctvpoint/backups"
RETENTION_DAYS=14

cd "$BACKEND_DIR"

# Refuse to run at all unless this checkout's own .env is actually pointed
# at the production database — this is what makes the hardcoded name above
# a real guardrail rather than just a comment.
if ! grep -q "DATABASE_URL=.*${PROD_DB_NAME}" .env; then
    echo "REFUSING TO RUN: $BACKEND_DIR/.env does not reference ${PROD_DB_NAME}." >&2
    echo "This script only ever runs against the production database." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "=== Nightly backup started: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
DUMP_FILE="$BACKUP_DIR/nightly_${TIMESTAMP}.sql.gz"

echo "--- Dumping ${PROD_DB_NAME} ---"
pg_dump -h localhost -U dukani "$PROD_DB_NAME" | gzip > "$DUMP_FILE"

DUMP_SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || stat -f%z "$DUMP_FILE")
if [ "$DUMP_SIZE" -lt 1000 ]; then
    echo "ERROR: dump file is suspiciously small (${DUMP_SIZE} bytes) — not pruning old backups, investigate before relying on this one." >&2
    exit 1
fi
echo "Backup written: $DUMP_FILE (${DUMP_SIZE} bytes)"

echo "--- Pruning backups older than ${RETENTION_DAYS} days ---"
find "$BACKUP_DIR" -name 'nightly_*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete

echo "=== Nightly backup finished: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
