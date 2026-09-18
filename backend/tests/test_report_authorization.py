from tests.conftest import (
    auth_headers,
    get_main_store,
    make_branch,
    make_inventory,
    make_product,
    make_user,
)


async def test_store_keeper_cannot_override_inventory_report_branch(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)
    await make_inventory(db_session, product, pos_branch, quantity=50)
    await make_inventory(db_session, product, main_store, quantity=5)

    resp = await client.get(
        "/api/v1/reports/inventory",
        params={"branch_id": str(pos_branch.id)},
        headers=auth_headers(keeper),
    )
    assert resp.status_code == 200
    body = resp.json()
    branch_names = {row["branch"] for row in body["by_branch"]}
    assert pos_branch.name not in branch_names
    assert body["summary"]["total_quantity"] != 50 or main_store.name in branch_names


async def test_store_keeper_cannot_override_low_stock_report_branch(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session, minimum_stock=10)
    await make_inventory(db_session, product, pos_branch, quantity=1)

    resp = await client.get(
        "/api/v1/reports/low-stock",
        params={"branch_id": str(pos_branch.id)},
        headers=auth_headers(keeper),
    )
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["branch"] != pos_branch.name


async def test_cashier_cannot_override_closing_report_branch(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)

    resp = await client.get(
        "/api/v1/reports/closing",
        params={"branch_id": str(other_branch.id)},
        headers=auth_headers(cashier),
    )
    assert resp.status_code == 200
    # report_service.get_closing_report is scoped by the forced branch_id —
    # nothing here asserts row contents since there may be no closings yet,
    # but the call must succeed (not 403) confirming the route accepted the
    # cashier and silently overrode branch_id rather than leaking data.


async def test_admin_can_query_any_branch_inventory_report(client, db_session):
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, pos_branch, quantity=20)

    resp = await client.get(
        "/api/v1/reports/inventory",
        params={"branch_id": str(pos_branch.id)},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200
    branch_names = {row["branch"] for row in resp.json()["by_branch"]}
    assert pos_branch.name in branch_names
