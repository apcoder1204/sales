#!/bin/bash
# =============================================================
# DUKANI POS — Stop Demo Mode & Restore Local Dev
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo ""
echo "Stopping demo mode..."

# Kill cloudflared
pkill -f "cloudflared" 2>/dev/null && echo "✓ Cloudflared stopped" || true

# Kill demo servers
if [ -f /tmp/dukani-vite.pid ]; then
  kill "$(cat /tmp/dukani-vite.pid)" 2>/dev/null || true
  rm /tmp/dukani-vite.pid
  echo "✓ Vite stopped"
fi
if [ -f /tmp/dukani-uvicorn.pid ]; then
  kill "$(cat /tmp/dukani-uvicorn.pid)" 2>/dev/null || true
  rm /tmp/dukani-uvicorn.pid
  echo "✓ Uvicorn stopped"
fi

# Restore normal dev mode (remove .env.local override)
rm -f "$FRONTEND_DIR/.env.local"
echo "✓ Restored local dev API URL"

echo ""
echo "Demo mode stopped. To resume local development:"
echo "  Terminal 1: cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  Terminal 2: cd frontend && npm run dev"
