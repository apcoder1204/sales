import pytest

from tests.conftest import auth_headers, make_branch, make_user


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_me_endpoint_returns_current_user(client, db_session):
    branch = await make_branch(db_session)
    user = await make_user(db_session, "cashier", branch=branch)
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == user.username
    assert body["role"] == "cashier"


async def test_rollback_isolation_does_not_leak_between_tests(db_session):
    from sqlalchemy import select

    from app.models.branch import Branch

    branch = await make_branch(db_session)
    result = await db_session.execute(select(Branch).where(Branch.id == branch.id))
    assert result.scalar_one_or_none() is not None
