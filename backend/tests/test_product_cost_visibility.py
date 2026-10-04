"""Product cost_price (Bei ya Ununuzi) is super_admin/admin only — not
visible to general_manager/store_keeper/cashier in any product response,
and not settable by them either (create ignores it, update strips it).
Creating a product must never require a cost_price — it defaults to 0 and
is set later by an admin/super_admin via edit."""
import uuid

from sqlalchemy import select

from app.models.category import Category
from tests.conftest import auth_headers, make_product, make_user

COST_VISIBLE_ROLES = ["super_admin", "admin"]
COST_HIDDEN_ROLES = ["general_manager", "store_keeper", "cashier"]


async def _make_category(db_session) -> Category:
    cat = Category(name=f"cat_{uuid.uuid4().hex[:8]}")
    db_session.add(cat)
    await db_session.flush()
    return cat


# ─── Read visibility ────────────────────────────────────────────────────────

async def test_list_products_omits_cost_for_cost_hidden_roles(client, db_session):
    product = await make_product(db_session)
    gm = await make_user(db_session, "general_manager")
    resp = await client.get("/api/v1/products", headers=auth_headers(gm))
    assert resp.status_code == 200
    row = next(p for p in resp.json()["items"] if p["id"] == str(product.id))
    assert row["cost_price"] is None


async def test_list_products_includes_cost_for_admin(client, db_session):
    product = await make_product(db_session)
    admin = await make_user(db_session, "admin")
    resp = await client.get("/api/v1/products", headers=auth_headers(admin))
    assert resp.status_code == 200
    row = next(p for p in resp.json()["items"] if p["id"] == str(product.id))
    assert float(row["cost_price"]) == float(product.cost_price)


async def test_get_product_omits_cost_for_store_keeper(client, db_session):
    product = await make_product(db_session)
    keeper = await make_user(db_session, "store_keeper")
    resp = await client.get(f"/api/v1/products/{product.id}", headers=auth_headers(keeper))
    assert resp.status_code == 200
    assert resp.json()["cost_price"] is None


async def test_get_product_includes_cost_for_super_admin(client, db_session):
    product = await make_product(db_session)
    sa = await make_user(db_session, "super_admin")
    resp = await client.get(f"/api/v1/products/{product.id}", headers=auth_headers(sa))
    assert resp.status_code == 200
    assert float(resp.json()["cost_price"]) == float(product.cost_price)


# ─── Create: cost_price never blocks, and is write-restricted ─────────────

async def test_create_product_without_cost_price_succeeds(client, db_session):
    cat = await _make_category(db_session)
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/products", headers=auth_headers(admin),
        json={"name": "No Cost Yet", "category_id": cat.id, "selling_price": "15000"},
    )
    assert resp.status_code == 201
    assert float(resp.json()["cost_price"]) == 0.0


async def test_general_manager_can_create_product_without_cost(client, db_session):
    cat = await _make_category(db_session)
    gm = await make_user(db_session, "general_manager")
    resp = await client.post(
        "/api/v1/products", headers=auth_headers(gm),
        json={"name": "GM Created Product", "category_id": cat.id, "selling_price": "20000"},
    )
    assert resp.status_code == 201
    # general_manager has no cost visibility, so the create response itself
    # must not reveal the (defaulted-to-0) cost_price either.
    assert resp.json()["cost_price"] is None


async def test_general_manager_submitted_cost_price_is_ignored_on_create(client, db_session):
    cat = await _make_category(db_session)
    gm = await make_user(db_session, "general_manager")
    resp = await client.post(
        "/api/v1/products", headers=auth_headers(gm),
        # Below selling_price so Pydantic's own selling-vs-cost validator
        # doesn't also fire — the point here is purely that the submitted
        # value is ignored server-side, not validator interaction.
        json={"name": "GM Tries Cost", "category_id": cat.id, "selling_price": "20000", "cost_price": "15000"},
    )
    assert resp.status_code == 201
    product_id = resp.json()["id"]

    from app.models.product import Product
    product = (await db_session.execute(select(Product).where(Product.id == uuid.UUID(product_id)))).scalar_one()
    assert float(product.cost_price) == 0.0


async def test_admin_submitted_cost_price_is_honored_on_create(client, db_session):
    cat = await _make_category(db_session)
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/products", headers=auth_headers(admin),
        json={"name": "Admin Sets Cost", "category_id": cat.id, "selling_price": "20000", "cost_price": "12000"},
    )
    assert resp.status_code == 201
    assert float(resp.json()["cost_price"]) == 12000.0


async def test_create_validator_still_rejects_selling_below_submitted_cost(client, db_session):
    cat = await _make_category(db_session)
    admin = await make_user(db_session, "admin")
    resp = await client.post(
        "/api/v1/products", headers=auth_headers(admin),
        json={"name": "Underpriced", "category_id": cat.id, "selling_price": "5000", "cost_price": "10000"},
    )
    assert resp.status_code == 422


# ─── Update: only admin/super_admin can set cost_price ────────────────────

async def test_general_manager_cannot_set_cost_price_on_update(client, db_session):
    product = await make_product(db_session)
    gm = await make_user(db_session, "general_manager")
    resp = await client.put(
        f"/api/v1/products/{product.id}", headers=auth_headers(gm),
        json={"cost_price": "77777"},
    )
    assert resp.status_code == 200

    from app.models.product import Product
    row = (await db_session.execute(select(Product).where(Product.id == product.id))).scalar_one()
    assert float(row.cost_price) == float(product.cost_price)  # unchanged


async def test_general_manager_update_response_does_not_leak_existing_cost(client, db_session):
    product = await make_product(db_session)
    gm = await make_user(db_session, "general_manager")
    resp = await client.put(
        f"/api/v1/products/{product.id}", headers=auth_headers(gm),
        json={"name": "Renamed By GM"},
    )
    assert resp.status_code == 200
    assert resp.json()["cost_price"] is None


async def test_admin_can_set_cost_price_on_update(client, db_session):
    product = await make_product(db_session)
    admin = await make_user(db_session, "admin")
    resp = await client.put(
        f"/api/v1/products/{product.id}", headers=auth_headers(admin),
        json={"cost_price": "54321"},
    )
    assert resp.status_code == 200
    assert float(resp.json()["cost_price"]) == 54321.0

    from app.models.product import Product
    row = (await db_session.execute(select(Product).where(Product.id == product.id))).scalar_one()
    assert float(row.cost_price) == 54321.0
