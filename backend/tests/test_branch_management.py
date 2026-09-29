"""Global Matawi/Branch registry management (super_admin/admin only) —
authorization matrix, CRUD, validation, and the safe-deletion rules."""
import uuid

import pytest
from sqlalchemy import select

from app.models.branch import Branch
from tests.conftest import auth_headers, make_branch, make_inventory, make_product, make_user

DENIED_ROLES = ["general_manager", "store_keeper", "cashier"]


# ─── Authorization matrix ──────────────────────────────────────────────────

async def test_super_admin_can_list_branches(client, db_session):
    user = await make_user(db_session, "super_admin")
    resp = await client.get("/api/v1/branches", headers=auth_headers(user))
    assert resp.status_code == 200


async def test_admin_can_list_branches(client, db_session):
    user = await make_user(db_session, "admin")
    resp = await client.get("/api/v1/branches", headers=auth_headers(user))
    assert resp.status_code == 200


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_denied_roles_cannot_list_branches(client, db_session, role):
    user = await make_user(db_session, role)
    resp = await client.get("/api/v1/branches", headers=auth_headers(user))
    assert resp.status_code == 403


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_denied_roles_cannot_create_branch(client, db_session, role):
    user = await make_user(db_session, role)
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(user),
        json={"name": "Should Not Exist", "code": "SNE1", "branch_type": "pos_point"},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_denied_roles_cannot_update_branch(client, db_session, role):
    branch = await make_branch(db_session)
    user = await make_user(db_session, role)
    resp = await client.patch(
        f"/api/v1/branches/{branch.id}", headers=auth_headers(user), json={"name": "Renamed"},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_denied_roles_cannot_delete_branch(client, db_session, role):
    branch = await make_branch(db_session)
    user = await make_user(db_session, role)
    resp = await client.delete(f"/api/v1/branches/{branch.id}", headers=auth_headers(user))
    assert resp.status_code == 403


async def test_unauthenticated_request_rejected(client):
    resp = await client.get("/api/v1/branches")
    assert resp.status_code == 401


# ─── CRUD ───────────────────────────────────────────────────────────────────

async def test_create_branch(client, db_session):
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": "Test Branch Alpha", "code": "tba1", "branch_type": "pos_point", "phone": "0700000000"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Branch Alpha"
    assert body["code"] == "TBA1"  # normalized uppercase
    assert body["is_active"] is True


async def test_get_branch(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    resp = await client.get(f"/api/v1/branches/{branch.id}", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(branch.id)


async def test_update_branch(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    resp = await client.patch(
        f"/api/v1/branches/{branch.id}", headers=auth_headers(admin),
        json={"name": "Renamed Branch", "phone": "0711111111"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Branch"
    assert resp.json()["phone"] == "0711111111"


# ─── Validation ─────────────────────────────────────────────────────────────

async def test_duplicate_branch_name_rejected(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": branch.name, "code": "UNIQ1", "branch_type": "pos_point"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "BRANCH_ALREADY_EXISTS"


async def test_duplicate_branch_code_rejected(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": "Totally Unique Name", "code": branch.code, "branch_type": "pos_point"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "BRANCH_ALREADY_EXISTS"


async def test_empty_branch_name_rejected(client, db_session):
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": "   ", "code": "EMPTY1", "branch_type": "pos_point"},
    )
    assert resp.status_code == 422


async def test_branch_code_with_spaces_rejected(client, db_session):
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": "Space Code Branch", "code": "AB CD", "branch_type": "pos_point"},
    )
    assert resp.status_code == 422


async def test_get_nonexistent_branch_404(client, db_session):
    import uuid
    admin = await make_user(db_session, "admin")
    resp = await client.get(f"/api/v1/branches/{uuid.uuid4()}", headers=auth_headers(admin))
    assert resp.status_code == 404


async def test_update_nonexistent_branch_404(client, db_session):
    import uuid
    admin = await make_user(db_session, "admin")
    resp = await client.patch(
        f"/api/v1/branches/{uuid.uuid4()}", headers=auth_headers(admin), json={"name": "Ghost Branch"},
    )
    assert resp.status_code == 404


async def test_delete_nonexistent_branch_404(client, db_session):
    import uuid
    admin = await make_user(db_session, "admin")
    resp = await client.delete(f"/api/v1/branches/{uuid.uuid4()}", headers=auth_headers(admin))
    assert resp.status_code == 404


# ─── Safe deletion ──────────────────────────────────────────────────────────

async def test_delete_branch_with_no_history_hard_deletes(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    resp = await client.delete(f"/api/v1/branches/{branch.id}", headers=auth_headers(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True
    assert body["deactivated"] is False

    row = (await db_session.execute(select(Branch).where(Branch.id == branch.id))).scalar_one_or_none()
    assert row is None


async def test_delete_branch_with_history_deactivates_instead(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=5)

    resp = await client.delete(f"/api/v1/branches/{branch.id}", headers=auth_headers(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is False
    assert body["deactivated"] is True

    row = (await db_session.execute(select(Branch).where(Branch.id == branch.id))).scalar_one()
    assert row.is_active is False


async def test_delete_freshly_api_created_branch_still_hard_deletes(client, db_session):
    """Regression: creating a branch through the real API (not the raw
    make_branch factory) writes a BRANCH_CREATED audit_log row with
    branch_id=<new branch>. That row must not itself count as "history" that
    blocks a hard delete — otherwise no branch created through the actual
    app can ever be hard-deleted, only deactivated, even with zero real
    business activity. Caught via manual browser verification, not by
    test_delete_branch_with_no_history_hard_deletes above (which uses the
    factory and so never creates that audit row in the first place)."""
    admin = await make_user(db_session, "admin")
    create_resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": "Fresh API Branch", "code": "FAB1", "branch_type": "pos_point"},
    )
    assert create_resp.status_code == 201
    branch_id = uuid.UUID(create_resp.json()["id"])

    resp = await client.delete(f"/api/v1/branches/{branch_id}", headers=auth_headers(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True
    assert body["deactivated"] is False

    row = (await db_session.execute(select(Branch).where(Branch.id == branch_id))).scalar_one_or_none()
    assert row is None


async def test_delete_branch_with_assigned_user_deactivates_instead(client, db_session):
    admin = await make_user(db_session, "admin")
    branch = await make_branch(db_session)
    await make_user(db_session, "cashier", branch=branch)

    resp = await client.delete(f"/api/v1/branches/{branch.id}", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["deactivated"] is True


# ─── Main-store invariant ───────────────────────────────────────────────────

async def test_cannot_deactivate_the_only_active_main_store(client, db_session):
    from tests.conftest import get_main_store

    admin = await make_user(db_session, "admin")
    main_store = await get_main_store(db_session)

    resp = await client.patch(
        f"/api/v1/branches/{main_store.id}", headers=auth_headers(admin), json={"is_active": False},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "LAST_ACTIVE_MAIN_STORE"


async def test_cannot_delete_the_only_active_main_store(client, db_session):
    from tests.conftest import get_main_store

    admin = await make_user(db_session, "admin")
    main_store = await get_main_store(db_session)

    resp = await client.delete(f"/api/v1/branches/{main_store.id}", headers=auth_headers(admin))
    assert resp.status_code == 400
    assert resp.json()["code"] == "LAST_ACTIVE_MAIN_STORE"


async def test_creating_second_active_main_store_rejected(client, db_session):
    """DB-level partial unique index (uq_branches_single_active_main_store,
    added when this invariant was first hardened) must still hold — the
    service layer doesn't duplicate this check on create, it relies on the
    constraint and converts the resulting IntegrityError cleanly. This also
    proves, structurally, why "deactivate a main store while another stays
    active" is never a reachable state: the DB guarantees at most one
    *active* main_store row can ever exist at a time, so the only path the
    service's last-active-main-store guard can ever take when the target
    branch is itself an active main store is "no other active one exists" —
    exactly the two cases already covered above."""
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/branches", headers=auth_headers(admin),
        json={"name": "Second Main Store", "code": "MAIN2", "branch_type": "main_store"},
    )
    assert resp.status_code == 409
