from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.role import Role
from tests.conftest import auth_headers, make_user


async def _role_id(db_session, name: str) -> int:
    row = (await db_session.execute(select(Role).where(Role.name == name))).scalar_one()
    return row.id


async def _last_audit_entry(db_session, action: str, entity_id):
    rows = (
        await db_session.execute(
            select(AuditLog)
            .where(AuditLog.action == action, AuditLog.entity_id == str(entity_id))
            .order_by(AuditLog.created_at.desc())
        )
    ).scalars().all()
    return rows[0] if rows else None


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


async def test_super_admin_can_deactivate_lower_role_user(client, db_session):
    super_admin = await make_user(db_session, "super_admin")
    cashier = await make_user(db_session, "cashier")

    resp = await client.delete(f"/api/v1/users/{cashier.id}", headers=auth_headers(super_admin))
    assert resp.status_code == 200


async def test_super_admin_can_deactivate_admin(client, db_session):
    super_admin = await make_user(db_session, "super_admin")
    admin = await make_user(db_session, "admin")

    resp = await client.delete(f"/api/v1/users/{admin.id}", headers=auth_headers(super_admin))
    assert resp.status_code == 200


async def test_super_admin_can_deactivate_another_super_admin(client, db_session):
    """Only self-deactivation is blocked for super_admin — deactivating a
    peer super_admin account is an intentional, permitted admin action."""
    super_admin = await make_user(db_session, "super_admin")
    other_super_admin = await make_user(db_session, "super_admin")

    resp = await client.delete(
        f"/api/v1/users/{other_super_admin.id}", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 200


async def test_admin_can_deactivate_lower_role_user(client, db_session):
    admin = await make_user(db_session, "admin")
    store_keeper = await make_user(db_session, "store_keeper")

    resp = await client.delete(f"/api/v1/users/{store_keeper.id}", headers=auth_headers(admin))
    assert resp.status_code == 200


async def test_cashier_cannot_delete_user(client, db_session):
    cashier = await make_user(db_session, "cashier")
    other = await make_user(db_session, "cashier")

    resp = await client.delete(f"/api/v1/users/{other.id}", headers=auth_headers(cashier))
    assert resp.status_code == 403


async def test_store_keeper_cannot_delete_user(client, db_session):
    keeper = await make_user(db_session, "store_keeper")
    other = await make_user(db_session, "cashier")

    resp = await client.delete(f"/api/v1/users/{other.id}", headers=auth_headers(keeper))
    assert resp.status_code == 403


async def test_general_manager_cannot_delete_user(client, db_session):
    """general_manager has cross-branch operational scope but, per the
    existing business model, no user-management permission at all — the
    route itself is gated to super_admin/admin only."""
    manager = await make_user(db_session, "general_manager")
    other = await make_user(db_session, "cashier")

    resp = await client.delete(f"/api/v1/users/{other.id}", headers=auth_headers(manager))
    assert resp.status_code == 403


async def test_deactivate_user_requires_auth(client, db_session):
    """Direct API call with no token at all must be rejected."""
    other = await make_user(db_session, "cashier")
    resp = await client.delete(f"/api/v1/users/{other.id}")
    assert resp.status_code == 401


# --- Audit behavior ---


async def test_successful_deactivation_is_audited(client, db_session):
    super_admin = await make_user(db_session, "super_admin")
    cashier = await make_user(db_session, "cashier")

    resp = await client.delete(f"/api/v1/users/{cashier.id}", headers=auth_headers(super_admin))
    assert resp.status_code == 200

    entry = await _last_audit_entry(db_session, "USER_DEACTIVATED", cashier.id)
    assert entry is not None
    assert entry.category == "users"
    assert entry.user_id == super_admin.id
    assert entry.username == super_admin.username
    assert entry.user_role == "super_admin"
    assert entry.details["username"] == cashier.username


async def test_admin_blocked_from_super_admin_is_audited(client, db_session):
    admin = await make_user(db_session, "admin")
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.delete(f"/api/v1/users/{super_admin.id}", headers=auth_headers(admin))
    assert resp.status_code == 403

    entry = await _last_audit_entry(db_session, "PERMISSION_DENIED", super_admin.id)
    assert entry is not None
    assert entry.category == "system"
    assert entry.user_id == admin.id
    assert entry.user_role == "admin"
    assert entry.details["reason"] == "admin_cannot_deactivate_hidden_role"

    # The blocked attempt must not have actually deactivated the account.
    from app.models.user import User

    row = (await db_session.execute(select(User).where(User.id == super_admin.id))).scalar_one()
    assert row.is_active is True


async def test_self_deactivation_attempt_is_audited(client, db_session):
    admin = await make_user(db_session, "admin")

    resp = await client.delete(f"/api/v1/users/{admin.id}", headers=auth_headers(admin))
    assert resp.status_code == 403

    entry = await _last_audit_entry(db_session, "PERMISSION_DENIED", admin.id)
    assert entry is not None
    assert entry.category == "system"
    assert entry.details["reason"] == "cannot_deactivate_self"

    from app.models.user import User

    row = (await db_session.execute(select(User).where(User.id == admin.id))).scalar_one()
    assert row.is_active is True


# --- Reactivation (PUT /users/{id} with is_active=true) ---


async def test_admin_can_reactivate_lower_role_user(client, db_session):
    from app.models.user import User

    admin = await make_user(db_session, "admin")
    cashier = await make_user(db_session, "cashier", is_active=False)

    resp = await client.put(
        f"/api/v1/users/{cashier.id}", headers=auth_headers(admin), json={"is_active": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    row = (await db_session.execute(select(User).where(User.id == cashier.id))).scalar_one()
    assert row.is_active is True


async def test_admin_cannot_reactivate_hidden_role_user(client, db_session):
    admin = await make_user(db_session, "admin")
    other_admin = await make_user(db_session, "admin", is_active=False)

    resp = await client.put(
        f"/api/v1/users/{other_admin.id}", headers=auth_headers(admin), json={"is_active": True}
    )
    assert resp.status_code == 403


async def test_super_admin_can_reactivate_admin(client, db_session):
    from app.models.user import User

    super_admin = await make_user(db_session, "super_admin")
    admin = await make_user(db_session, "admin", is_active=False)

    resp = await client.put(
        f"/api/v1/users/{admin.id}", headers=auth_headers(super_admin), json={"is_active": True}
    )
    assert resp.status_code == 200

    row = (await db_session.execute(select(User).where(User.id == admin.id))).scalar_one()
    assert row.is_active is True


async def test_cannot_reactivate_self_via_user_management(client, db_session):
    """Symmetric with self-deactivation being blocked — a deactivated actor
    couldn't reach this endpoint anyway (get_current_user rejects inactive
    users before role checks), but the self-target guard in update_user
    still applies unconditionally regardless of the fields being changed."""
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.put(
        f"/api/v1/users/{super_admin.id}", headers=auth_headers(super_admin), json={"is_active": True}
    )
    assert resp.status_code == 403


# --- Permanent deletion (DELETE /users/{id}/permanent) ---


async def test_super_admin_can_permanently_delete_user_with_no_history(client, db_session):
    from app.models.user import User

    super_admin = await make_user(db_session, "super_admin")
    cashier = await make_user(db_session, "cashier")

    resp = await client.delete(
        f"/api/v1/users/{cashier.id}/permanent", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 200

    row = (
        await db_session.execute(select(User).where(User.id == cashier.id))
    ).scalar_one_or_none()
    assert row is None


async def test_permanent_delete_blocked_when_user_made_a_sale(client, db_session):
    from tests.conftest import make_branch, make_inventory, make_product

    super_admin = await make_user(db_session, "super_admin")
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale_resp = await client.post(
        "/api/v1/sales",
        headers=auth_headers(cashier),
        json={
            "branch_id": str(branch.id), "payment_method": "cash",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert sale_resp.status_code == 201

    resp = await client.delete(
        f"/api/v1/users/{cashier.id}/permanent", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 400

    from app.models.user import User

    row = (await db_session.execute(select(User).where(User.id == cashier.id))).scalar_one_or_none()
    assert row is not None  # not deleted


async def test_permanent_delete_blocked_when_user_closed_a_day(client, db_session):
    from tests.conftest import make_branch

    super_admin = await make_user(db_session, "super_admin")
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)

    close_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": 0, "expenses": []},
    )
    assert close_resp.status_code == 201

    resp = await client.delete(
        f"/api/v1/users/{admin.id}/permanent", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 400


async def test_admin_cannot_permanently_delete_super_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.delete(
        f"/api/v1/users/{super_admin.id}/permanent", headers=auth_headers(admin)
    )
    assert resp.status_code == 403


async def test_admin_cannot_permanently_delete_another_admin(client, db_session):
    admin = await make_user(db_session, "admin")
    other_admin = await make_user(db_session, "admin")

    resp = await client.delete(
        f"/api/v1/users/{other_admin.id}/permanent", headers=auth_headers(admin)
    )
    assert resp.status_code == 403


async def test_cannot_permanently_delete_self(client, db_session):
    super_admin = await make_user(db_session, "super_admin")

    resp = await client.delete(
        f"/api/v1/users/{super_admin.id}/permanent", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 403


async def test_cashier_cannot_permanently_delete_anyone(client, db_session):
    cashier = await make_user(db_session, "cashier")
    other = await make_user(db_session, "cashier")

    resp = await client.delete(
        f"/api/v1/users/{other.id}/permanent", headers=auth_headers(cashier)
    )
    assert resp.status_code == 403


async def test_permanent_deletion_is_audited(client, db_session):
    super_admin = await make_user(db_session, "super_admin")
    cashier = await make_user(db_session, "cashier")
    cashier_id = cashier.id
    cashier_username = cashier.username

    resp = await client.delete(
        f"/api/v1/users/{cashier_id}/permanent", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 200

    entry = await _last_audit_entry(db_session, "USER_PERMANENTLY_DELETED", cashier_id)
    assert entry is not None
    assert entry.category == "users"
    assert entry.user_id == super_admin.id
    assert entry.details["username"] == cashier_username


async def test_permanent_delete_blocked_attempt_is_audited(client, db_session):
    from tests.conftest import make_branch, make_inventory, make_product

    super_admin = await make_user(db_session, "super_admin")
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    await client.post(
        "/api/v1/sales",
        headers=auth_headers(cashier),
        json={
            "branch_id": str(branch.id), "payment_method": "cash",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )

    resp = await client.delete(
        f"/api/v1/users/{cashier.id}/permanent", headers=auth_headers(super_admin)
    )
    assert resp.status_code == 400

    entry = await _last_audit_entry(db_session, "PERMISSION_DENIED", cashier.id)
    assert entry is not None
    assert entry.details["reason"] == "user_has_history"
    assert entry.details["history"]["sales_made"] == 1
