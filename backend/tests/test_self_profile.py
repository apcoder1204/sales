from sqlalchemy import select

from app.models.user import User
from tests.conftest import auth_headers, make_user


async def test_user_can_edit_own_profile(client, db_session):
    user = await make_user(db_session, "cashier")
    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user),
        json={"full_name": "New Name", "email": "new@example.com"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["email"] == "new@example.com"


async def test_get_me_includes_email(client, db_session):
    user = await make_user(db_session, "cashier")
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert "email" in resp.json()


async def test_username_change_is_unique(client, db_session):
    user_a = await make_user(db_session, "cashier")
    user_b = await make_user(db_session, "cashier")

    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user_a),
        json={"username": user_b.username},
    )
    assert resp.status_code == 409


async def test_username_change_to_new_value_succeeds(client, db_session):
    user = await make_user(db_session, "cashier")
    new_username = f"{user.username}_renamed"

    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user),
        json={"username": new_username},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == new_username

    # Old username no longer resolves to this account; new one does, and the
    # user's identity (id) is unchanged — a rename, not a new account.
    row = (
        await db_session.execute(select(User).where(User.username == new_username))
    ).scalar_one()
    assert row.id == user.id


async def test_username_can_keep_its_own_value(client, db_session):
    """Submitting your own current username back should not collide with
    the uniqueness check against yourself."""
    user = await make_user(db_session, "cashier")
    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user),
        json={"username": user.username, "full_name": "Still Me"},
    )
    assert resp.status_code == 200


async def test_password_change_requires_correct_current_password(client, db_session):
    user = await make_user(db_session, "cashier", password="Original1234")
    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user),
        json={
            "current_password": "WrongPassword1",
            "new_password": "BrandNew1234",
            "confirm_password": "BrandNew1234",
        },
    )
    assert resp.status_code == 400


async def test_password_change_rejects_weak_password(client, db_session):
    user = await make_user(db_session, "cashier", password="Original1234")
    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user),
        json={
            "current_password": "Original1234",
            "new_password": "short",
            "confirm_password": "short",
        },
    )
    assert resp.status_code == 422


async def test_password_change_succeeds_and_invalidates_old_session(client, db_session):
    user = await make_user(db_session, "cashier", password="Original1234")
    old_headers = auth_headers(user)

    resp = await client.put(
        "/api/v1/auth/me",
        headers=old_headers,
        json={
            "current_password": "Original1234",
            "new_password": "BrandNew1234",
            "confirm_password": "BrandNew1234",
        },
    )
    assert resp.status_code == 200

    # The token used to make this very change is now stale (token_version
    # bumped), matching logout/password-reset behavior.
    stale_resp = await client.get("/api/v1/auth/me", headers=old_headers)
    assert stale_resp.status_code == 401

    # Old password no longer works; new one does.
    old_login = await client.post(
        "/api/v1/auth/login", json={"username": user.username, "password": "Original1234"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login", json={"username": user.username, "password": "BrandNew1234"}
    )
    assert new_login.status_code == 200


async def test_user_cannot_edit_another_users_profile_via_direct_api(client, db_session):
    """PUT /auth/me only ever targets the caller's own account — there is no
    user_id in the payload/URL to manipulate, so this is inherently IDOR-safe,
    but verify a second user's data is truly untouched by the first user's call."""
    user_a = await make_user(db_session, "cashier")
    user_b = await make_user(db_session, "cashier")

    resp = await client.put(
        "/api/v1/auth/me",
        headers=auth_headers(user_a),
        json={"full_name": "Only A Should Change"},
    )
    assert resp.status_code == 200

    b_row = (await db_session.execute(select(User).where(User.id == user_b.id))).scalar_one()
    assert b_row.full_name != "Only A Should Change"


async def test_profile_update_requires_auth(client, db_session):
    resp = await client.put("/api/v1/auth/me", json={"full_name": "Nobody"})
    assert resp.status_code == 401


async def test_password_hash_never_returned(client, db_session):
    user = await make_user(db_session, "cashier")
    resp = await client.put(
        "/api/v1/auth/me", headers=auth_headers(user), json={"full_name": "X"}
    )
    assert resp.status_code == 200
    assert "password" not in resp.json()
    assert "password_hash" not in resp.json()
