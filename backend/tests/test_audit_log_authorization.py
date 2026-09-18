from tests.conftest import (
    auth_headers,
    get_main_store,
    make_branch,
    make_product,
    make_user,
)


async def _adjust_stock(client, admin, product, branch, qty=5):
    resp = await client.post(
        "/api/v1/inventory/adjust",
        headers=auth_headers(admin),
        json={
            "product_id": str(product.id),
            "branch_id": str(branch.id),
            "quantity": qty,
            "type": "stock_in",
            "notes": "audit log fixture",
        },
    )
    assert resp.status_code == 200


async def test_store_keeper_cannot_see_another_branch_audit_logs(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    admin = await make_user(db_session, "admin")
    keeper = await make_user(db_session, "store_keeper")
    product_main = await make_product(db_session)
    product_pos = await make_product(db_session)

    await _adjust_stock(client, admin, product_main, main_store)
    await _adjust_stock(client, admin, product_pos, pos_branch)

    resp = await client.get("/api/v1/audit-logs", headers=auth_headers(keeper))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["category"] == "inventory"
    # The pos_branch adjustment's entity_id is that inventory row's own id —
    # simplest robust check is on details.product matching only the
    # main-store fixture, never the pos_branch one.
    products_seen = {item["details"].get("product") for item in body["items"] if item["details"]}
    assert product_main.name in products_seen
    assert product_pos.name not in products_seen


async def test_gm_category_override_rejected(client, db_session):
    admin = await make_user(db_session, "admin")
    gm = await make_user(db_session, "general_manager")

    # Create a "users" category audit event.
    resp = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin),
        json={
            "username": "audit_test_user",
            "full_name": "Audit Test",
            "password": "Test1234",
            "confirm_password": "Test1234",
            "role_id": gm.role_id,
        },
    )
    assert resp.status_code == 201

    # GM explicitly tries to read the "users" category — must be forced back
    # to "transfers" regardless of what it asked for.
    override_resp = await client.get(
        "/api/v1/audit-logs", params={"category": "users"}, headers=auth_headers(gm)
    )
    assert override_resp.status_code == 200
    for item in override_resp.json()["items"]:
        assert item["category"] == "transfers"


async def test_admin_retains_global_audit_visibility(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    admin = await make_user(db_session, "admin")
    product_main = await make_product(db_session)
    product_pos = await make_product(db_session)

    await _adjust_stock(client, admin, product_main, main_store)
    await _adjust_stock(client, admin, product_pos, pos_branch)

    resp = await client.get(
        "/api/v1/audit-logs", params={"category": "inventory"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 200
    products_seen = {
        item["details"].get("product") for item in resp.json()["items"] if item["details"]
    }
    assert product_main.name in products_seen
    assert product_pos.name in products_seen


async def test_cashier_cannot_access_audit_logs(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    resp = await client.get("/api/v1/audit-logs", headers=auth_headers(cashier))
    assert resp.status_code == 403
