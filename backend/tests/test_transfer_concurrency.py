from tests.conftest import (
    auth_headers,
    get_main_store,
    make_branch,
    make_inventory,
    make_product,
    make_user,
)


async def _create_request(client, cashier, main_store, product, qty=3):
    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(cashier),
        json={
            "reason": "concurrency test",
            "from_branch_id": str(main_store.id),
            "to_branch_id": str(cashier.branch_id),
            "items": [{"product_id": str(product.id), "quantity": qty}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_double_approval_rejected(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    req = await _create_request(client, cashier, main_store, product, qty=3)
    item_id = req["items"][0]["id"]
    approval = {"items": [{"item_id": item_id, "approved_qty": 3}], "notes": "ok"}

    first = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/approve", headers=auth_headers(admin), json=approval
    )
    assert first.status_code == 200

    second = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/approve", headers=auth_headers(admin), json=approval
    )
    assert second.status_code == 400


async def test_approval_after_rejection_rejected(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    req = await _create_request(client, cashier, main_store, product, qty=3)
    item_id = req["items"][0]["id"]

    reject_resp = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/reject",
        headers=auth_headers(admin),
        json={"notes": "no stock for you"},
    )
    assert reject_resp.status_code == 200

    approve_resp = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/approve",
        headers=auth_headers(admin),
        json={"items": [{"item_id": item_id, "approved_qty": 3}], "notes": "too late"},
    )
    assert approve_resp.status_code == 400


async def test_double_rejection_rejected(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    req = await _create_request(client, cashier, main_store, product, qty=3)

    first = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/reject", headers=auth_headers(admin), json={"notes": "no"}
    )
    assert first.status_code == 200
    second = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/reject", headers=auth_headers(admin), json={"notes": "no"}
    )
    assert second.status_code == 400


async def test_execute_before_approval_rejected(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    req = await _create_request(client, cashier, main_store, product, qty=3)

    resp = await client.post(
        f"/api/v1/transfers/requests/{req['id']}/execute", headers=auth_headers(cashier)
    )
    assert resp.status_code == 400


async def test_double_execution_rejected(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    admin = await make_user(db_session, "admin")
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    req = await _create_request(client, cashier, main_store, product, qty=3)
    item_id = req["items"][0]["id"]
    await client.put(
        f"/api/v1/transfers/requests/{req['id']}/approve",
        headers=auth_headers(admin),
        json={"items": [{"item_id": item_id, "approved_qty": 3}], "notes": "ok"},
    )

    # Execution is a handover from whoever holds the stock (store_keeper,
    # since from_branch is the main store) — not the requesting cashier.
    first = await client.post(
        f"/api/v1/transfers/requests/{req['id']}/execute", headers=auth_headers(keeper)
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/transfers/requests/{req['id']}/execute", headers=auth_headers(keeper)
    )
    assert second.status_code == 400


async def test_fulfilled_request_cannot_execute_again_via_storekeeper(client, db_session):
    """Same as above but executed once by the storekeeper side of the
    handover, confirming the fulfilled status sticks regardless of who
    re-attempts it."""
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    admin = await make_user(db_session, "admin")
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    req = await _create_request(client, cashier, main_store, product, qty=3)
    item_id = req["items"][0]["id"]
    await client.put(
        f"/api/v1/transfers/requests/{req['id']}/approve",
        headers=auth_headers(admin),
        json={"items": [{"item_id": item_id, "approved_qty": 3}], "notes": "ok"},
    )
    first = await client.post(
        f"/api/v1/transfers/requests/{req['id']}/execute", headers=auth_headers(keeper)
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/transfers/requests/{req['id']}/execute", headers=auth_headers(keeper)
    )
    assert second.status_code == 400


async def test_approval_cannot_exceed_available_stock(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=pos_branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=2)

    req = await _create_request(client, cashier, main_store, product, qty=5)
    item_id = req["items"][0]["id"]

    resp = await client.put(
        f"/api/v1/transfers/requests/{req['id']}/approve",
        headers=auth_headers(admin),
        json={"items": [{"item_id": item_id, "approved_qty": 5}], "notes": "too much"},
    )
    assert resp.status_code == 400
