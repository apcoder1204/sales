#!/bin/bash
# Resets the DEMO database to a clean, freshly-generated dataset.
#
# Safety: the target database name is hardcoded below, never taken from an
# argument or from the process's own DATABASE_URL/.env — this script must
# never be able to run against production by a copy-paste or fat-finger
# mistake. It refuses to run unless it can positively confirm the backend
# it's operating on is configured for the demo database.
#
# Intended to run as a nightly cron job on the demo instance only:
#   0 3 * * * /opt/dukanipos-demo/backend/scripts/reset_demo_data.sh >> /home/cctvpoint/demo-reset.log 2>&1
set -euo pipefail

DEMO_DB_NAME="dukani_pos_demo"
DEMO_SERVICE="dukani-pos-demo"
BACKEND_DIR="/opt/dukanipos-demo/backend"

cd "$BACKEND_DIR"

# Refuse to run at all unless this checkout's own .env is actually pointed
# at the demo database — this is what makes the hardcoded name above a real
# guardrail rather than just a comment.
if ! grep -q "DATABASE_URL=.*${DEMO_DB_NAME}" .env; then
    echo "REFUSING TO RUN: $BACKEND_DIR/.env does not reference ${DEMO_DB_NAME}." >&2
    echo "This script only ever runs against the demo database." >&2
    exit 1
fi

echo "=== Demo data reset started: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

echo "--- Stopping ${DEMO_SERVICE} ---"
sudo -n systemctl stop "$DEMO_SERVICE"

echo "--- Regenerating demo data ---"
.venv/bin/python -m app.db.seed_demo

echo "--- Starting ${DEMO_SERVICE} ---"
sudo -n systemctl start "$DEMO_SERVICE"
sleep 2
sudo -n systemctl is-active "$DEMO_SERVICE"

echo "=== Demo data reset finished: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
