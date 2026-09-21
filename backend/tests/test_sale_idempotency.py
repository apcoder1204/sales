"""POST /sales Idempotency-Key support — a retried or double-submitted
checkout (network timeout, a double-tap before the button disables) must
never create a second sale or deduct stock twice."""
from sqlalchemy import select

from app.models.sale import Sale
from tests.conftest import auth_headers, make_branch, make_inventory, make_product, make_user


async def _sale_payload(branch, product, qty=2):
    return {
        "branch_id": str(branch.id),
        "payment_method": "cash",
        "items": [{"product_id": str(product.id), "quantity": qty}],
    }


async def _inventory_qty(client, admin, branch, product):
    resp = await client.get(
        "/api/v1/inventory", params={"branch_id": str(branch.id)}, headers=auth_headers(admin)
    )
    for item in resp.json()["items"]:
        if item["id"] == str(product.id):
            for stock in item["inventory"]:
                if stock["branch_id"] == str(branch.id):
                    return stock["quantity"]
    return None


async def test_repeated_key_returns_same_sale_and_deducts_stock_once(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    headers = {**auth_headers(cashier), "Idempotency-Key": "retry-key-1"}
    payload = await _sale_payload(branch, product, qty=3)

    first = await client.post("/api/v1/sales", headers=headers, json=payload)
    assert first.status_code == 201
    first_sale_id = first.json()["sale"]["id"]

    second = await client.post("/api/v1/sales", headers=headers, json=payload)
    assert second.status_code == 201
    assert second.json()["sale"]["id"] == first_sale_id
    assert second.json() == first.json()

    rows = (await db_session.execute(select(Sale).where(Sale.branch_id == branch.id))).scalars().all()
    assert len(rows) == 1

    qty = await _inventory_qty(client, admin, branch, product)
    assert qty == 7  # deducted once, not twice


async def test_different_keys_create_separate_sales(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    payload = await _sale_payload(branch, product, qty=2)

    first = await client.post(
        "/api/v1/sales", headers={**auth_headers(cashier), "Idempotency-Key": "key-a"}, json=payload
    )
    second = await client.post(
        "/api/v1/sales", headers={**auth_headers(cashier), "Idempotency-Key": "key-b"}, json=payload
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["sale"]["id"] != second.json()["sale"]["id"]

    qty = await _inventory_qty(client, admin, branch, product)
    assert qty == 6  # two independent sales of 2 each


async def test_no_key_behaves_as_before(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    payload = await _sale_payload(branch, product, qty=1)
    first = await client.post("/api/v1/sales", headers=auth_headers(cashier), json=payload)
    second = await client.post("/api/v1/sales", headers=auth_headers(cashier), json=payload)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["sale"]["id"] != second.json()["sale"]["id"]

    qty = await _inventory_qty(client, admin, branch, product)
    assert qty == 8  # no key => no dedup, two sales as normal


async def test_same_key_different_users_do_not_collide(client, db_session):
    branch = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch)
    cashier_b = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    payload = await _sale_payload(branch, product, qty=1)
    resp_a = await client.post(
        "/api/v1/sales", headers={**auth_headers(cashier_a), "Idempotency-Key": "shared-key"}, json=payload
    )
    resp_b = await client.post(
        "/api/v1/sales", headers={**auth_headers(cashier_b), "Idempotency-Key": "shared-key"}, json=payload
    )
    assert resp_a.status_code == 201 and resp_b.status_code == 201
    assert resp_a.json()["sale"]["id"] != resp_b.json()["sale"]["id"]
