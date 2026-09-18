from tests.conftest import (
    auth_headers,
    get_main_store,
    make_branch,
    make_inventory,
    make_product,
    make_user,
)


async def test_store_keeper_cannot_adjust_pos_branch(client, db_session):
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/inventory/adjust",
        headers=auth_headers(keeper),
        json={
            "product_id": str(product.id),
            "branch_id": str(pos_branch.id),
            "quantity": 5,
            "type": "stock_in",
            "notes": "attempted cross-branch adjust",
        },
    )
    assert resp.status_code == 403


async def test_store_keeper_can_adjust_main_store(client, db_session):
    main_store = await get_main_store(db_session)
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/inventory/adjust",
        headers=auth_headers(keeper),
        json={
            "product_id": str(product.id),
            "branch_id": str(main_store.id),
            "quantity": 5,
            "type": "stock_in",
            "notes": "legit main store adjust",
        },
    )
    assert resp.status_code == 200


async def test_cashier_cannot_adjust_inventory_at_all(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/inventory/adjust",
        headers=auth_headers(cashier),
        json={
            "product_id": str(product.id),
            "branch_id": str(branch.id),
            "quantity": 5,
            "type": "stock_in",
            "notes": "cashier should not reach this route",
        },
    )
    assert resp.status_code == 403


async def test_store_keeper_cannot_query_another_branch_low_stock(client, db_session):
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    keeper = await make_user(db_session, "store_keeper")
    main_store = await get_main_store(db_session)

    # A product low on stock at the POS branch but not at the main store —
    # if branch scoping is bypassed, this shows up in the response.
    product = await make_product(db_session, minimum_stock=10)
    await make_inventory(db_session, product, pos_branch, quantity=1)
    await make_inventory(db_session, product, main_store, quantity=999)

    resp = await client.get(
        "/api/v1/inventory/low-stock",
        params={"branch_id": str(pos_branch.id)},
        headers=auth_headers(keeper),
    )
    assert resp.status_code == 200
    # The store_keeper-supplied pos_branch.id must be silently overridden to
    # the main store, not honored.
    for item in resp.json():
        assert item["branch"] == main_store.name
        assert item["product"] != product.name


async def test_cashier_cannot_access_another_branch_inventory(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)

    resp = await client.get(
        "/api/v1/inventory",
        params={"branch_id": str(other_branch.id)},
        headers=auth_headers(cashier),
    )
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        for stock in item["inventory"]:
            assert str(stock["branch_id"]) == str(own_branch.id)


async def test_unauthorized_available_source_access_rejected(client, db_session):
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)

    resp = await client.get(
        "/api/v1/inventory/available-sources",
        params={
            "product_id": str(product.id),
            "quantity": 1,
            "destination_branch_id": str(other_branch.id),
        },
        headers=auth_headers(cashier),
    )
    assert resp.status_code == 403


async def test_cashier_can_query_available_sources_for_own_branch(client, db_session):
    own_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)

    resp = await client.get(
        "/api/v1/inventory/available-sources",
        params={
            "product_id": str(product.id),
            "quantity": 1,
            "destination_branch_id": str(own_branch.id),
        },
        headers=auth_headers(cashier),
    )
    assert resp.status_code == 200
