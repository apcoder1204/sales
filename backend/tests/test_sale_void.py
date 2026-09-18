from tests.conftest import auth_headers, make_branch, make_inventory, make_product, make_user


async def _make_sale(client, cashier, product, qty=2):
    resp = await client.post(
        "/api/v1/sales",
        headers=auth_headers(cashier),
        json={
            "branch_id": str(cashier.branch_id),
            "payment_method": "cash",
            "items": [{"product_id": str(product.id), "quantity": qty}],
        },
    )
    assert resp.status_code == 201
    return resp.json()["sale"]


async def _inventory_qty(client, admin, branch, product):
    resp = await client.get(
        "/api/v1/inventory",
        params={"branch_id": str(branch.id)},
        headers=auth_headers(admin),
    )
    for item in resp.json()["items"]:
        if item["id"] == str(product.id):
            for stock in item["inventory"]:
                if stock["branch_id"] == str(branch.id):
                    return stock["quantity"]
    return None


async def test_void_restores_exact_inventory(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    qty_before_sale = await _inventory_qty(client, admin, branch, product)
    assert qty_before_sale == 10

    sale = await _make_sale(client, cashier, product, qty=3)
    qty_after_sale = await _inventory_qty(client, admin, branch, product)
    assert qty_after_sale == 7

    resp = await client.post(
        f"/api/v1/sales/{sale['id']}/void",
        headers=auth_headers(admin),
        json={"reason": "customer returned everything"},
    )
    assert resp.status_code == 200

    qty_after_void = await _inventory_qty(client, admin, branch, product)
    assert qty_after_void == qty_before_sale == 10


async def test_void_creates_reversal_ledger_entry(client, db_session):
    from sqlalchemy import select

    from app.models.inventory_transaction import InventoryTransaction

    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, cashier, product, qty=4)
    resp = await client.post(
        f"/api/v1/sales/{sale['id']}/void",
        headers=auth_headers(admin),
        json={"reason": "wrong item"},
    )
    assert resp.status_code == 200

    rows = (
        await db_session.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.reference_id == sale["id"],
                InventoryTransaction.reference_type == "sale_void",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    tx = rows[0]
    assert tx.quantity_change == 4
    assert tx.quantity_after == tx.quantity_before + 4
    assert tx.transaction_type == "stock_in"


async def test_double_void_cannot_restore_twice(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, cashier, product, qty=3)

    first = await client.post(
        f"/api/v1/sales/{sale['id']}/void", headers=auth_headers(admin), json={"reason": "first void"}
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/sales/{sale['id']}/void", headers=auth_headers(admin), json={"reason": "second void"}
    )
    assert second.status_code == 400

    qty = await _inventory_qty(client, admin, branch, product)
    assert qty == 10  # not 13 — restored exactly once


async def test_void_nonexistent_sale_404(client, db_session):
    import uuid

    admin = await make_user(db_session, "admin")
    resp = await client.post(
        f"/api/v1/sales/{uuid.uuid4()}/void",
        headers=auth_headers(admin),
        json={"reason": "sale does not exist"},
    )
    assert resp.status_code == 404


async def test_void_across_closed_day_rejected(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, cashier, product, qty=2)

    close_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={"branch_id": str(branch.id), "counted_cash": 0, "expenses": []},
    )
    assert close_resp.status_code == 201

    void_resp = await client.post(
        f"/api/v1/sales/{sale['id']}/void", headers=auth_headers(admin), json={"reason": "too late"}
    )
    assert void_resp.status_code == 400

    qty = await _inventory_qty(client, admin, branch, product)
    assert qty == 8  # untouched — void was rejected


async def test_cashier_cannot_void_sale(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, cashier, product, qty=1)
    resp = await client.post(
        f"/api/v1/sales/{sale['id']}/void", headers=auth_headers(cashier), json={"reason": "self void"}
    )
    assert resp.status_code == 403
