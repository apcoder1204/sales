from tests.conftest import (
    auth_headers,
    get_main_store,
    make_branch,
    make_inventory,
    make_product,
    make_user,
)


def _request_payload(from_branch_id, to_branch_id, product_id, qty=1):
    return {
        "reason": "Test stock request",
        "from_branch_id": str(from_branch_id),
        "to_branch_id": str(to_branch_id),
        "items": [{"product_id": str(product_id), "quantity": qty}],
    }


async def test_unauthorized_request_destination_rejected(client, db_session):
    """Cashier tries to have stock delivered to someone else's branch."""
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    main_store = await get_main_store(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(cashier),
        json=_request_payload(main_store.id, other_branch.id, product.id),
    )
    assert resp.status_code == 403


async def test_unauthorized_request_source_rejected(client, db_session):
    """Cashier tries to source stock from somewhere other than the main store."""
    own_branch = await make_branch(db_session)
    other_branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(cashier),
        json=_request_payload(other_branch.id, own_branch.id, product.id),
    )
    assert resp.status_code == 403


async def test_cashier_can_request_from_main_store_to_own_branch(client, db_session):
    own_branch = await make_branch(db_session)
    main_store = await get_main_store(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(cashier),
        json=_request_payload(main_store.id, own_branch.id, product.id),
    )
    assert resp.status_code == 201


async def test_store_keeper_cannot_spoof_source_branch(client, db_session):
    """store_keeper tries to create a request between two branches that
    don't involve the main store at all."""
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(keeper),
        json=_request_payload(branch_a.id, branch_b.id, product.id),
    )
    assert resp.status_code == 403


async def test_invalid_branch_rejected_on_create_request(client, db_session):
    import uuid

    own_branch = await make_branch(db_session)
    main_store = await get_main_store(db_session)
    cashier = await make_user(db_session, "cashier", branch=own_branch)
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(cashier),
        json=_request_payload(main_store.id, uuid.uuid4(), product.id),
    )
    assert resp.status_code in (403, 404)


async def test_inactive_branch_rejected_on_create_request(client, db_session):
    own_branch = await make_branch(db_session)
    inactive_branch = await make_branch(db_session, is_active=False)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(admin),
        json=_request_payload(inactive_branch.id, own_branch.id, product.id),
    )
    assert resp.status_code == 400


async def test_same_source_and_destination_rejected(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)

    resp = await client.post(
        "/api/v1/transfers/requests",
        headers=auth_headers(admin),
        json=_request_payload(branch.id, branch.id, product.id),
    )
    assert resp.status_code == 400


# --- Direct transfers (Phase 5) ---


async def test_store_keeper_cannot_direct_transfer_from_pos_branch(client, db_session):
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    other_branch = await make_branch(db_session)
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)
    await make_inventory(db_session, product, pos_branch, quantity=10)

    resp = await client.post(
        "/api/v1/transfers",
        headers=auth_headers(keeper),
        json={
            "from_branch_id": str(pos_branch.id),
            "to_branch_id": str(other_branch.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 403


async def test_direct_transfer_rejects_inactive_destination(client, db_session):
    main_store = await get_main_store(db_session)
    inactive_branch = await make_branch(db_session, is_active=False)
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    resp = await client.post(
        "/api/v1/transfers",
        headers=auth_headers(keeper),
        json={
            "from_branch_id": str(main_store.id),
            "to_branch_id": str(inactive_branch.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 400


async def test_store_keeper_can_direct_transfer_from_main_store(client, db_session):
    main_store = await get_main_store(db_session)
    pos_branch = await make_branch(db_session, branch_type="pos_point")
    keeper = await make_user(db_session, "store_keeper")
    product = await make_product(db_session)
    await make_inventory(db_session, product, main_store, quantity=10)

    resp = await client.post(
        "/api/v1/transfers",
        headers=auth_headers(keeper),
        json={
            "from_branch_id": str(main_store.id),
            "to_branch_id": str(pos_branch.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201
