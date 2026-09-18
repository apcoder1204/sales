#!/bin/bash
# URGENT FIX: the webhook-deploy pipeline has been silently failing to
# restart the backend on every push since at least 2026-09-18 07:17:55 UTC.
#
# Root cause: dukani-deploy-webhook.service has NoNewPrivileges=true. That
# flag applies to the whole process tree it spawns — including deploy.sh's
# `sudo -n systemctl restart dukani-pos` call — and systemd-level
# NoNewPrivileges blocks sudo from escalating at all, regardless of sudoers
# rules. deploy.sh's `set -e` doesn't catch this because the failing command
# is the second-to-last step; the script logs the sudo error and continues
# to the health check, which still passes (the OLD process is still up), so
# the deploy silently "succeeds" while never actually restarting anything.
#
# Effect: git pull / rsync / pip install / alembic upgrade all worked on
# every push, but the running gunicorn process kept serving whatever code
# was live at the last MANUAL restart. The DB schema has been correctly
# migrated ahead of the running code this whole time — that part is safe,
# migrations are additive. Backend restarts have simply not been happening.
#
# Run ONCE, with sudo:
#   sudo bash deploy/fix_webhook_privileges.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this with sudo: sudo bash deploy/fix_webhook_privileges.sh" >&2
    exit 1
fi

UNIT="/etc/systemd/system/dukani-deploy-webhook.service"
BACKUP="/etc/systemd/system/dukani-deploy-webhook.service.bak.$(date +%Y%m%d%H%M%S)"

if [ ! -f "$UNIT" ]; then
    echo "ERROR: $UNIT not found — is this the right server?" >&2
    exit 1
fi

if ! grep -q "^NoNewPrivileges=true" "$UNIT"; then
    echo "NoNewPrivileges=true not found in $UNIT — nothing to fix, or already fixed."
    exit 0
fi

cp "$UNIT" "$BACKUP"
echo "Backed up $UNIT -> $BACKUP"

sed -i '/^NoNewPrivileges=true/d' "$UNIT"
echo "Removed NoNewPrivileges=true from $UNIT"

systemctl daemon-reload
systemctl restart dukani-deploy-webhook
sleep 2
systemctl is-active dukani-deploy-webhook

echo ""
echo "Fixed. Verify with a real push: after the next 'git push origin main',"
echo "check that 'systemctl show dukani-pos --property=ActiveEnterTimestamp'"
echo "updates to a fresh timestamp (currently checkable via:"
echo "  systemctl show dukani-pos --property=ActiveEnterTimestamp"
echo "and comparing against the time of your next push)."
