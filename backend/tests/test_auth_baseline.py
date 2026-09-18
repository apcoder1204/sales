"""Baseline auth regression tests — not new fixes, but the Phase 12
checklist explicitly requires these covered and none existed before."""
from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from tests.conftest import auth_headers, make_user

UTC = timezone.utc


async def test_inactive_user_rejected(client, db_session):
    user = await make_user(db_session, "cashier", is_active=False)
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(user))
    assert resp.status_code == 403


async def test_locked_user_rejected(client, db_session):
    user = await make_user(db_session, "cashier")
    headers = auth_headers(user)
    user.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=30)
    await db_session.flush()
    # locked_until is a TIMESTAMPTZ column — a real request re-fetches the
    # user in a fresh session and gets back a tz-aware value; force that
    # same round-trip here instead of comparing against the still-naive
    # Python value this test just assigned in memory (see
    # test_lockout_after_failed_logins_returns_423_not_500 for why that
    # distinction matters). Expiring after capturing `headers` (rather than
    # before) avoids a synchronous lazy-load of user.id outside an async
    # context when auth_headers() reads it.
    db_session.expire(user)

    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 423


async def test_lockout_after_failed_logins_returns_423_not_500(client, db_session):
    """locked_until reads back tz-aware (TIMESTAMPTZ column) while every
    other 'now' in this codebase is naive-but-UTC by convention — comparing
    the two directly in Python raises TypeError instead of enforcing the
    lockout, surfacing as an opaque 500 instead of a clean 423. Exercise the
    real failed-login path (not a directly-assigned locked_until) so this
    actually goes through a fresh DB read of the tz-aware column.

    Pre-seeds 4 failed attempts directly (MAX_LOGIN_ATTEMPTS - 1) rather
    than making 4 real login calls: RATE_LIMIT_LOGIN (5/minute) is a
    separate protective layer, keyed the same way across every test in this
    process, and this test only needs to isolate the lockout comparison
    itself, not re-prove the rate limiter."""
    user = await make_user(db_session, "cashier", password="Correct12345")
    user.failed_login_attempts = 4
    await db_session.flush()

    # 5th failure — crosses MAX_LOGIN_ATTEMPTS and sets locked_until.
    fifth_attempt = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "WrongPassword1"},
    )
    assert fifth_attempt.status_code == 401

    # Now locked — even the correct password must cleanly report the
    # lockout (423), not crash with a raw 500.
    locked_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "Correct12345"},
    )
    assert locked_resp.status_code == 423


async def test_invalid_jwt_rejected(client):
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


async def test_missing_token_rejected(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_token_version_bump_invalidates_old_token(client, db_session):
    user = await make_user(db_session, "cashier")
    old_token_headers = auth_headers(user)

    logout_resp = await client.post("/api/v1/auth/logout", headers=old_token_headers)
    assert logout_resp.status_code == 200

    resp = await client.get("/api/v1/auth/me", headers=old_token_headers)
    assert resp.status_code == 401


async def test_role_and_branch_changes_take_effect_immediately(client, db_session):
    """Authorization reads role/branch fresh from the DB on every request
    (never trusts the JWT's embedded claims) — so an admin changing a user's
    role takes effect on that user's very next request, no re-login needed."""
    from sqlalchemy import select

    from app.models.role import Role

    user = await make_user(db_session, "cashier")
    headers = auth_headers(user)

    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.json()["role"] == "cashier"

    admin_role = (await db_session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
    user.role_id = admin_role.id
    await db_session.flush()
    # In production each request gets its own fresh session (see get_db), so
    # there's no identity-map staleness — the test harness shares one session
    # across "requests", so it must force that same freshness explicitly.
    db_session.expire(user)

    me_resp_2 = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp_2.json()["role"] == "admin"
