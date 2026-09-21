"""GET /sales/{id} and GET /sales/{id}/receipt — a cashier may only view
their own sales (anti-enumeration: a mismatch looks like 404, not 403, so a
cashier can't tell someone else's sale ID exists at all)."""
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


async def test_owner_cashier_can_view_own_sale_and_receipt(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, cashier, product)

    detail = await client.get(f"/api/v1/sales/{sale['id']}", headers=auth_headers(cashier))
    assert detail.status_code == 200
    assert detail.json()["id"] == sale["id"]

    receipt = await client.get(f"/api/v1/sales/{sale['id']}/receipt", headers=auth_headers(cashier))
    assert receipt.status_code == 200
    assert receipt.json()["transaction_no"] == sale["transaction_no"]


async def test_other_cashier_gets_404_not_403(client, db_session):
    branch = await make_branch(db_session)
    owner = await make_user(db_session, "cashier", branch=branch)
    other = await make_user(db_session, "cashier", branch=branch)
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, owner, product)

    detail = await client.get(f"/api/v1/sales/{sale['id']}", headers=auth_headers(other))
    assert detail.status_code == 404

    receipt = await client.get(f"/api/v1/sales/{sale['id']}/receipt", headers=auth_headers(other))
    assert receipt.status_code == 404


async def test_admin_can_view_any_sale(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _make_sale(client, cashier, product)

    detail = await client.get(f"/api/v1/sales/{sale['id']}", headers=auth_headers(admin))
    assert detail.status_code == 200


async def test_get_sale_nonexistent_404(client, db_session):
    import uuid

    admin = await make_user(db_session, "admin")
    resp = await client.get(f"/api/v1/sales/{uuid.uuid4()}", headers=auth_headers(admin))
    assert resp.status_code == 404
