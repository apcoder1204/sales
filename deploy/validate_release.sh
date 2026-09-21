#!/bin/bash
# Release validation gate — run before any production/demo deploy, and
# before building any distributable archive of this codebase.
#
# This exists because of a real incident this session: a "codebase
# snapshot" archive was built by hand-picking directories to exclude
# (node_modules, .venv, ...) rather than mirroring .gitignore, and it
# accidentally included a real private key (backend/homlab.pem). The key
# was never committed to git and the archive was caught and deleted before
# anyone downloaded it — but that was luck, not a check. This script is
# the check.
#
# Exit code 0 = safe to deploy/release. Any nonzero = STOP, do not deploy.
set -uo pipefail

cd "$(dirname "$0")/.."
FAILED=0

section() { echo ""; echo "=== $1 ==="; }
pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; FAILED=1; }

# ── 1. Secrets never tracked by git ─────────────────────────────────────────
section "Secret-file scan (git-tracked files)"
SECRET_PATTERNS='\.pem$|\.key$|\.ppk$|\.pfx$|id_rsa|id_ed25519|\.env$'
# frontend/.env is the one intentional exception: Vite's committed
# dev-default (VITE_API_BASE_URL=http://localhost:8000 — no secret), not to
# be confused with frontend/.env.local or .env.production, which carry real
# values and are correctly gitignored, never excluded from this scan.
TRACKED_SECRETS=$(git ls-files | grep -E "$SECRET_PATTERNS" | grep -v -E '\.env\.example$|\.env\.sample$|^frontend/\.env$' || true)
if [ -n "$TRACKED_SECRETS" ]; then
    fail "git-tracked files match secret-file patterns:"
    echo "$TRACKED_SECRETS" | sed 's/^/    /'
else
    pass "no secret-shaped filenames are tracked by git"
fi

# Same scan against full git history, not just the current tree — catches a
# secret that was committed once and later deleted (still recoverable from
# history, .gitignore only stops *future* additions).
HISTORICAL_SECRETS=$(git log --all --diff-filter=A --name-only --pretty=format: | grep -E "$SECRET_PATTERNS" | grep -v -E '\.env\.example$|\.env\.sample$|^frontend/\.env$' | sort -u || true)
if [ -n "$HISTORICAL_SECRETS" ]; then
    fail "secret-shaped filenames were added at some point in git history (may still be recoverable even if since deleted):"
    echo "$HISTORICAL_SECRETS" | sed 's/^/    /'
else
    pass "no secret-shaped filenames appear anywhere in git history"
fi

# ── 2. Backend: compiles, migrations at head, tests pass ───────────────────
section "Backend checks"
if [ -d backend/.venv ]; then
    # shellcheck disable=SC1091
    source backend/.venv/bin/activate
    (cd backend && python -m compileall -q app/) && pass "backend compiles" || fail "backend compile errors"
    (cd backend && python -m pytest -q) > /tmp/release_validate_pytest.log 2>&1
    if [ $? -eq 0 ]; then
        pass "backend test suite ($(grep -oE '[0-9]+ passed' /tmp/release_validate_pytest.log | tail -1))"
    else
        fail "backend test suite — see /tmp/release_validate_pytest.log"
    fi
    HEADS=$(cd backend && alembic heads 2>/dev/null | grep -c '(head)')
    if [ "$HEADS" -eq 1 ]; then
        pass "exactly one alembic head"
    else
        fail "alembic has $HEADS heads — expected exactly 1 (unmerged migration branches?)"
    fi
else
    fail "backend/.venv not found — cannot run backend checks (run from a machine with the dev env set up)"
fi

# ── 3. Frontend: builds clean, translations in parity ───────────────────────
section "Frontend checks"
if [ -d frontend/node_modules ]; then
    (cd frontend && npx vite build --mode production) > /tmp/release_validate_build.log 2>&1
    if [ $? -eq 0 ]; then
        pass "frontend production build"
    else
        fail "frontend build — see /tmp/release_validate_build.log"
    fi

    node --experimental-vm-modules -e "
      import('$(pwd)/frontend/src/constants/translations/en.js').then(async m => {
        const en = m.default;
        const sw = (await import('$(pwd)/frontend/src/constants/translations/sw.js')).default;
        function flatten(o, p='') { let r=[]; for (const k in o) { const v=o[k]; const full=p?p+'.'+k:k; if (v && typeof v==='object' && !Array.isArray(v)) r=r.concat(flatten(v, full)); else r.push(full); } return r; }
        const enKeys = flatten(en).sort();
        const swKeys = flatten(sw).sort();
        const missing = enKeys.filter(k=>!swKeys.includes(k)).concat(swKeys.filter(k=>!enKeys.includes(k)));
        if (missing.length) { console.error('MISMATCH:', missing.join(', ')); process.exit(1); }
        console.log('OK', enKeys.length);
      });
    " > /tmp/release_validate_parity.log 2>&1
    if [ $? -eq 0 ]; then
        pass "en/sw translation key parity ($(grep -oE '[0-9]+' /tmp/release_validate_parity.log | tail -1) keys)"
    else
        fail "en/sw translation key parity — see /tmp/release_validate_parity.log"
    fi
else
    fail "frontend/node_modules not found — run npm install first"
fi

# ── Summary ──────────────────────────────────────────────────────────────
section "Summary"
if [ "$FAILED" -eq 0 ]; then
    echo "  ALL CHECKS PASSED — safe to deploy/release."
    exit 0
else
    echo "  ONE OR MORE CHECKS FAILED — do not deploy/release until fixed."
    exit 1
fi
