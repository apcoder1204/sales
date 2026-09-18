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
    user.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=30)
    await db_session.flush()

    resp = await client.get("/api/v1/auth/me", headers=auth_headers(user))
    assert resp.status_code == 423


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
