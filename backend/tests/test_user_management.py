from sqlalchemy import select

from app.models.role import Role
from tests.conftest import auth_headers, make_user


async def _role_id(db_session, name: str) -> int:
    row = (await db_session.execute(select(Role).where(Role.name == name))).scalar_one()
    return row.id


async def test_admin_cannot_see_admin_or_super_admin_in_list(client, db_session):
    admin = await make_user(db_session, "admin")
    other_admin = await make_user(db_session, "admin")
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.get("/api/v1/users", headers=auth_headers(admin))
    assert resp.status_code == 200
    usernames = {u["username"] for u in resp.json()["items"]}
    assert other_admin.username not in usernames
    assert super_admin.username not in usernames


async def test_super_admin_sees_everyone(client, db_session):
    super_admin = await make_user(db_session, "super_admin")
    admin = await make_user(db_session, "admin")

    resp = await client.get("/api/v1/users", headers=auth_headers(super_admin))
    assert resp.status_code == 200
    usernames = {u["username"] for u in resp.json()["items"]}
    assert admin.username in usernames


async def test_admin_cannot_create_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    admin_role_id = await _role_id(db_session, "admin")

    resp = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin),
        json={
            "username": "sneaky_admin",
            "full_name": "Sneaky",
            "password": "Test1234",
            "confirm_password": "Test1234",
            "role_id": admin_role_id,
        },
    )
    assert resp.status_code == 403


async def test_admin_cannot_create_super_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    sa_role_id = await _role_id(db_session, "super_admin")

    resp = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin),
        json={
            "username": "sneaky_super",
            "full_name": "Sneaky",
            "password": "Test1234",
            "confirm_password": "Test1234",
            "role_id": sa_role_id,
        },
    )
    assert resp.status_code == 403


async def test_admin_cannot_edit_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    other_admin = await make_user(db_session, "admin")

    resp = await client.put(
        f"/api/v1/users/{other_admin.id}",
        headers=auth_headers(admin),
        json={"full_name": "Renamed"},
    )
    assert resp.status_code == 403


async def test_admin_cannot_edit_super_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.put(
        f"/api/v1/users/{super_admin.id}",
        headers=auth_headers(admin),
        json={"full_name": "Renamed"},
    )
    assert resp.status_code == 403


async def test_admin_cannot_deactivate_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    other_admin = await make_user(db_session, "admin")

    resp = await client.delete(f"/api/v1/users/{other_admin.id}", headers=auth_headers(admin))
    assert resp.status_code == 403


async def test_admin_cannot_deactivate_super_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.delete(f"/api/v1/users/{super_admin.id}", headers=auth_headers(admin))
    assert resp.status_code == 403


async def test_admin_cannot_deactivate_itself(client, db_session):
    admin = await make_user(db_session, "admin")

    resp = await client.delete(f"/api/v1/users/{admin.id}", headers=auth_headers(admin))
    assert resp.status_code == 403


async def test_super_admin_cannot_deactivate_itself(client, db_session):
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.delete(f"/api/v1/users/{super_admin.id}", headers=auth_headers(super_admin))
    assert resp.status_code == 403


async def test_admin_cannot_escalate_itself_to_super_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    sa_role_id = await _role_id(db_session, "super_admin")

    resp = await client.put(
        f"/api/v1/users/{admin.id}",
        headers=auth_headers(admin),
        json={"role_id": sa_role_id},
    )
    assert resp.status_code == 403


async def test_super_admin_cannot_change_own_role_via_user_management(client, db_session):
    super_admin = await make_user(db_session, "super_admin")
    admin_role_id = await _role_id(db_session, "admin")

    resp = await client.put(
        f"/api/v1/users/{super_admin.id}",
        headers=auth_headers(super_admin),
        json={"role_id": admin_role_id},
    )
    assert resp.status_code == 403


async def test_admin_can_manage_cashier(client, db_session):
    admin = await make_user(db_session, "admin")
    cashier = await make_user(db_session, "cashier")

    resp = await client.put(
        f"/api/v1/users/{cashier.id}",
        headers=auth_headers(admin),
        json={"full_name": "Renamed Cashier"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed Cashier"
