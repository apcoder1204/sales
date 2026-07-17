#!/bin/bash
# =============================================================
# DUKANI POS — Demo / Tunnel Mode
# Exposes the app via a public Cloudflare URL for demonstrations.
#
# REMOVE THIS BEFORE PRODUCTION DEPLOYMENT.
# In production, configure a real web server (nginx/caddy) and
# set VITE_API_BASE_URL to the actual backend API URL.
# =============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
VITE_PID_FILE="/tmp/dukani-vite.pid"
UVICORN_PID_FILE="/tmp/dukani-uvicorn.pid"
VITE_LOG="/tmp/dukani-vite.log"
UVICORN_LOG="/tmp/dukani-uvicorn.log"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     DUKANI POS  —  Demo Mode         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Switch frontend to proxy/relative API URLs ──────────────
echo "[1/4] Switching frontend to tunnel mode..."
echo "VITE_API_BASE_URL=" > "$FRONTEND_DIR/.env.local"
echo "      ✓ API calls will route through Vite proxy"

# ── 2. Stop any running Vite / uvicorn ────────────────────────
echo "[2/4] Stopping existing dev servers..."
pkill -f "vite" 2>/dev/null && echo "      ✓ Vite stopped" || echo "      - Vite was not running"
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "      ✓ Uvicorn stopped" || echo "      - Uvicorn was not running"
sleep 1

# ── 3. Start backend ──────────────────────────────────────────
echo "[3/4] Starting backend..."
cd "$BACKEND_DIR"
source .venv/bin/activate
uvicorn app.main:app --port 8000 --host 127.0.0.1 > "$UVICORN_LOG" 2>&1 &
echo $! > "$UVICORN_PID_FILE"

# Wait for backend
for i in {1..10}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "      ✓ Backend ready"
    break
  fi
  sleep 1
done

# ── 4. Start frontend ─────────────────────────────────────────
echo "[4/4] Starting frontend..."
cd "$FRONTEND_DIR"
npm run dev > "$VITE_LOG" 2>&1 &
echo $! > "$VITE_PID_FILE"

# Wait for Vite
for i in {1..15}; do
  if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "      ✓ Frontend ready"
    break
  fi
  sleep 1
done

# ── Start cloudflared tunnel ──────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Starting Cloudflare Tunnel..."
echo "  Press Ctrl+C to stop the demo."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Use named tunnel config if available, otherwise fall back to random URL
TUNNEL_CONFIG="$HOME/.cloudflared/config.yml"
if [ -f "$TUNNEL_CONFIG" ] && ! grep -q "<TUNNEL_ID>" "$TUNNEL_CONFIG"; then
  # Named tunnel — permanent URL defined in config.yml
  DOMAIN=$(grep "hostname:" "$TUNNEL_CONFIG" | head -1 | awk '{print $2}')
  echo "  URL: https://$DOMAIN"
  echo ""
  cloudflared tunnel --config "$TUNNEL_CONFIG" run
else
  # No named tunnel configured — use temporary random URL
  echo "  (No named tunnel configured — using temporary URL)"
  echo "  See cloudflared-config.yml for permanent URL setup."
  echo ""
  cloudflared tunnel --url http://localhost:5173 --no-autoupdate 2>&1 | \
    grep --line-buffered -E "trycloudflare|INF|ERR|https://"
fi
