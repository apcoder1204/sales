#!/bin/bash
# One-time bootstrap for the DUKANI POS demo environment (demo.cctvpoint.org).
#
# Run ONCE, on the production server, as the cctvpoint user, with sudo:
#   sudo bash deploy/bootstrap_demo.sh
#
# What it does:
#   - Creates an isolated Postgres role + database for the demo (own random
#     password, generated here and never leaving this server)
#   - Populates /opt/dukanipos-demo/{backend,frontend/dist} from the current
#     source checkout + the already-built production frontend
#   - Creates and starts a new systemd service (dukani-pos-demo, port 8001)
#   - Adds an nginx vhost for demo.cctvpoint.org
#   - Adds a demo.cctvpoint.org ingress rule to the existing Cloudflare Tunnel
#   - Grants cctvpoint passwordless sudo for the demo service only (mirrors
#     the existing dukani-pos NOPASSWD entries), so ongoing deploys/resets
#     don't need a password
#   - Runs the demo data seed script once
#
# Idempotent: safe to re-run if a step fails partway through.
#
# After this runs successfully, add the DNS record shown at the end (that
# part needs the Cloudflare dashboard — this script can't do it).
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this with sudo: sudo bash deploy/bootstrap_demo.sh" >&2
    exit 1
fi

SRC_DIR="/home/cctvpoint/dukani-src"
DEMO_ROOT="/opt/dukanipos-demo"
DEMO_BACKEND="$DEMO_ROOT/backend"
DEMO_FRONTEND="$DEMO_ROOT/frontend/dist"
DEMO_DB="dukani_pos_demo"
DEMO_DB_USER="dukani_demo"
DEMO_PORT=8001
DEMO_SERVICE="dukani-pos-demo"
PYENV_PYTHON="/home/cctvpoint/.pyenv/versions/3.12.3/bin/python"
TUNNEL_CONFIG="/etc/cloudflared/config.yml"
CLOUDFLARE_TUNNEL_ID="355c7061-d488-4be9-98db-05198eaa8722"
DEMO_HOSTNAME="demo.cctvpoint.org"

echo "=== 1/9: Directories ==="
mkdir -p "$DEMO_BACKEND" "$DEMO_ROOT/frontend"
chown -R cctvpoint:cctvpoint "$DEMO_ROOT"

echo "=== 2/9: Postgres role + database ==="
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DEMO_DB_USER}'" | grep -q 1; then
    DEMO_DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    sudo -u postgres psql -c "CREATE ROLE ${DEMO_DB_USER} WITH LOGIN PASSWORD '${DEMO_DB_PASSWORD}';"
    echo "$DEMO_DB_PASSWORD" > /root/.dukani_demo_db_password
    chmod 600 /root/.dukani_demo_db_password
    echo "Created role ${DEMO_DB_USER} (password saved to /root/.dukani_demo_db_password)"
else
    DEMO_DB_PASSWORD=$(cat /root/.dukani_demo_db_password)
    echo "Role ${DEMO_DB_USER} already exists, reusing saved password"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DEMO_DB}'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE ${DEMO_DB} OWNER ${DEMO_DB_USER};"
    echo "Created database ${DEMO_DB}"
else
    echo "Database ${DEMO_DB} already exists"
fi

echo "=== 3/9: Backend code + venv ==="
rsync -a --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
  --exclude 'tests' --exclude '.pytest_cache' \
  --exclude 'pytest.ini' --exclude 'requirements-dev.txt' \
  "$SRC_DIR/backend/" "$DEMO_BACKEND/"
chown -R cctvpoint:cctvpoint "$DEMO_BACKEND"

if [ ! -d "$DEMO_BACKEND/.venv" ]; then
    sudo -u cctvpoint "$PYENV_PYTHON" -m venv "$DEMO_BACKEND/.venv"
fi
sudo -u cctvpoint "$DEMO_BACKEND/.venv/bin/pip" install -q -r "$DEMO_BACKEND/requirements.txt"

echo "=== 4/9: Demo .env ==="
if [ ! -f "$DEMO_BACKEND/.env" ]; then
    DEMO_SECRET_KEY=$(openssl rand -base64 48 | tr -d '/+=' | head -c 64)
    cat > "$DEMO_BACKEND/.env" << EOF
DATABASE_URL=postgresql+asyncpg://${DEMO_DB_USER}:${DEMO_DB_PASSWORD}@localhost:5432/${DEMO_DB}
SECRET_KEY=${DEMO_SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_MINUTES=15
BCRYPT_ROUNDS=12
DEBUG=false
ENVIRONMENT=demo
CORS_ORIGINS=["https://${DEMO_HOSTNAME}"]
FRONTEND_URL=https://${DEMO_HOSTNAME}
PASSWORD_RESET_EXPIRE_MINUTES=20
RATE_LIMIT_LOGIN=5/minute
RATE_LIMIT_DEFAULT=100/minute
EOF
    chown cctvpoint:cctvpoint "$DEMO_BACKEND/.env"
    chmod 600 "$DEMO_BACKEND/.env"
    echo "Wrote $DEMO_BACKEND/.env"
else
    echo "$DEMO_BACKEND/.env already exists, leaving it alone"
fi

echo "=== 5/9: Migrate + seed ==="
sudo -u cctvpoint bash -c "cd '$DEMO_BACKEND' && .venv/bin/alembic upgrade head"
sudo -u cctvpoint bash -c "cd '$DEMO_BACKEND' && .venv/bin/python -m app.db.seed_demo"

echo "=== 6/9: Frontend (reuse the already-built production dist) ==="
if [ -d "$SRC_DIR/frontend/dist" ]; then
    rsync -a --delete "$SRC_DIR/frontend/dist/" "$DEMO_FRONTEND/"
    chown -R cctvpoint:cctvpoint "$DEMO_ROOT/frontend"
else
    echo "WARNING: $SRC_DIR/frontend/dist not found — run the normal deploy.sh once first, then re-run this script." >&2
fi

echo "=== 7/9: systemd service ==="
cat > "/etc/systemd/system/${DEMO_SERVICE}.service" << EOF
[Unit]
Description=DUKANI POS FastAPI Application (DEMO)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple

User=cctvpoint
Group=cctvpoint

WorkingDirectory=${DEMO_BACKEND}

EnvironmentFile=${DEMO_BACKEND}/.env

ExecStart=${DEMO_BACKEND}/.venv/bin/gunicorn \\
    -k uvicorn.workers.UvicornWorker \\
    -w 2 \\
    -b 127.0.0.1:${DEMO_PORT} \\
    --access-logfile - \\
    --error-logfile - \\
    app.main:app

Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Write to a temp file and validate BEFORE installing — a malformed file
# directly in /etc/sudoers.d/ takes effect immediately (sudoers.d is read on
# every sudo invocation, no reload needed) and could break sudo entirely.
SUDOERS_TMP=$(mktemp)
cat > "$SUDOERS_TMP" << EOF
cctvpoint ALL=(root) NOPASSWD: /usr/bin/systemctl restart ${DEMO_SERVICE}, /usr/bin/systemctl status ${DEMO_SERVICE}, /usr/bin/systemctl is-active ${DEMO_SERVICE}, /usr/bin/systemctl stop ${DEMO_SERVICE}, /usr/bin/systemctl start ${DEMO_SERVICE}
EOF
visudo -c -f "$SUDOERS_TMP"
chmod 440 "$SUDOERS_TMP"
mv "$SUDOERS_TMP" "/etc/sudoers.d/dukani-deploy-demo"
chown root:root "/etc/sudoers.d/dukani-deploy-demo"

systemctl daemon-reload
systemctl enable "$DEMO_SERVICE"
systemctl restart "$DEMO_SERVICE"
sleep 2
systemctl is-active "$DEMO_SERVICE"

echo "=== 8/9: nginx vhost ==="
cat > "/etc/nginx/sites-available/dukani-pos-demo" << EOF
server {
    listen 80;
    listen [::]:80;

    server_name ${DEMO_HOSTNAME};

    root ${DEMO_FRONTEND};
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${DEMO_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location = /health {
        proxy_pass http://127.0.0.1:${DEMO_PORT}/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF
ln -sf /etc/nginx/sites-available/dukani-pos-demo /etc/nginx/sites-enabled/dukani-pos-demo
nginx -t
systemctl reload nginx

echo "=== 9/9: Cloudflare Tunnel ingress ==="
if ! grep -q "$DEMO_HOSTNAME" "$TUNNEL_CONFIG"; then
    python3 - "$TUNNEL_CONFIG" "$DEMO_HOSTNAME" << 'PYEOF'
import sys
path, hostname = sys.argv[1], sys.argv[2]
with open(path) as f:
    lines = f.readlines()
out = []
inserted = False
for line in lines:
    if not inserted and line.strip().startswith("- service: http_status:404"):
        out.append(f"  - hostname: {hostname}\n    service: http://localhost:80\n")
        inserted = True
    out.append(line)
with open(path, "w") as f:
    f.writelines(out)
PYEOF
    echo "Added ${DEMO_HOSTNAME} ingress rule to ${TUNNEL_CONFIG}"
    systemctl restart cloudflared
else
    echo "${DEMO_HOSTNAME} already present in ${TUNNEL_CONFIG}"
fi

echo ""
echo "=========================================================="
echo "Bootstrap complete."
echo ""
echo "MANUAL STEP STILL NEEDED (Cloudflare dashboard, not scriptable here):"
echo "  Add a DNS record:"
echo "    Type:  CNAME"
echo "    Name:  demo"
echo "    Target: ${CLOUDFLARE_TUNNEL_ID}.cfargotunnel.com"
echo "    Proxy status: Proxied (orange cloud)"
echo ""
echo "Once DNS propagates, verify with:"
echo "    curl https://${DEMO_HOSTNAME}/health"
echo "=========================================================="
