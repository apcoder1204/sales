"""Profit & Loss report (super_admin/admin/general_manager only).

Revenue/COGS come from SaleItem's own historical price/cost snapshot (not
Product's current values), operating expenses come from DailyClosingExpense
with the shortage-vs-surplus distinction applied, and everything is scoped
through the existing branch_context/business-date machinery — see
report_service.get_profit_loss_report for the full rationale."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.models.sale import Sale
from app.models.product import Product
from tests.conftest import auth_headers, get_main_store, make_branch, make_inventory, make_product, make_user

DENIED_ROLES = ["store_keeper", "cashier"]
ALLOWED_ROLES = ["super_admin", "admin", "general_manager"]


async def _sell(client, cashier, product, qty=1, payment_method="cash"):
    resp = await client.post(
        "/api/v1/sales",
        headers=auth_headers(cashier),
        json={
            "branch_id": str(cashier.branch_id),
            "payment_method": payment_method,
            "items": [{"product_id": str(product.id), "quantity": qty}],
        },
    )
    assert resp.status_code == 201
    return resp.json()["sale"]


async def _pl(client, user, **params):
    resp = await client.get("/api/v1/reports/profit-loss", headers=auth_headers(user), params=params)
    return resp


# ─── Authorization ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ALLOWED_ROLES)
async def test_allowed_roles_can_view_profit_loss(client, db_session, role):
    user = await make_user(db_session, role)
    resp = await _pl(client, user, period="month")
    assert resp.status_code == 200


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_denied_roles_cannot_view_profit_loss(client, db_session, role):
    branch = await make_branch(db_session)
    user = await make_user(db_session, role, branch=branch)
    resp = await _pl(client, user, period="month")
    assert resp.status_code == 403


async def test_unauthenticated_request_rejected(client):
    resp = await client.get("/api/v1/reports/profit-loss", params={"period": "month"})
    assert resp.status_code == 401


@pytest.mark.parametrize("role", DENIED_ROLES)
async def test_denied_roles_cannot_bypass_via_branch_id_param(client, db_session, role):
    other_branch = await make_branch(db_session)
    branch = await make_branch(db_session)
    user = await make_user(db_session, role, branch=branch)
    resp = await _pl(client, user, period="month", branch_id=str(other_branch.id))
    assert resp.status_code == 403


async def test_nonexistent_branch_id_returns_404(client, db_session):
    import uuid
    admin = await make_user(db_session, "admin")
    resp = await _pl(client, admin, period="month", branch_id=str(uuid.uuid4()))
    assert resp.status_code == 404


# ─── Revenue / COGS ─────────────────────────────────────────────────────────

async def test_single_sale_revenue_and_cogs(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price = Decimal("50000")
    product.selling_price = Decimal("80000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    await _sell(client, cashier, product, qty=2)

    resp = await _pl(client, admin, period="today", branch_id=str(branch.id))
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["revenue"] == 160000.0
    assert summary["cost_of_goods_sold"] == 100000.0
    assert summary["gross_profit"] == 60000.0
    assert summary["status"] == "profit"


async def test_multiple_products_and_quantities(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    p1 = await make_product(db_session)
    p1.cost_price, p1.selling_price = Decimal("10000"), Decimal("15000")
    p2 = await make_product(db_session)
    p2.cost_price, p2.selling_price = Decimal("20000"), Decimal("30000")
    db_session.add_all([p1, p2])
    await db_session.flush()
    await make_inventory(db_session, p1, branch, quantity=20)
    await make_inventory(db_session, p2, branch, quantity=20)

    await _sell(client, cashier, p1, qty=3)   # revenue 45000, cogs 30000
    await _sell(client, cashier, p2, qty=2)   # revenue 60000, cogs 40000

    resp = await _pl(client, admin, period="today", branch_id=str(branch.id))
    summary = resp.json()["summary"]
    assert summary["revenue"] == 105000.0
    assert summary["cost_of_goods_sold"] == 70000.0
    assert summary["gross_profit"] == 35000.0
    assert len(resp.json()["products"]) == 2


async def test_voided_sale_excluded_from_revenue(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("50000"), Decimal("80000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _sell(client, cashier, product, qty=1)

    before = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert before["summary"]["revenue"] == 80000.0

    void_resp = await client.post(
        f"/api/v1/sales/{sale['id']}/void",
        headers=auth_headers(admin),
        json={"reason": "test void for P&L exclusion"},
    )
    assert void_resp.status_code == 200

    after = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert after["summary"]["revenue"] == 0.0
    assert after["summary"]["cost_of_goods_sold"] == 0.0


async def test_different_branches_isolated(client, db_session):
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch_a)
    cashier_b = await make_user(db_session, "cashier", branch=branch_b)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("10000"), Decimal("20000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch_a, quantity=10)
    await make_inventory(db_session, product, branch_b, quantity=10)

    await _sell(client, cashier_a, product, qty=1)
    await _sell(client, cashier_b, product, qty=3)

    resp_a = (await _pl(client, admin, period="today", branch_id=str(branch_a.id))).json()
    resp_b = (await _pl(client, admin, period="today", branch_id=str(branch_b.id))).json()
    assert resp_a["summary"]["revenue"] == 20000.0
    assert resp_b["summary"]["revenue"] == 60000.0


# ─── Historical cost integrity (the critical test) ─────────────────────────

async def test_historical_cost_unaffected_by_later_product_cost_change(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("50000"), Decimal("80000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    await _sell(client, cashier, product, qty=2)

    original = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert original["summary"]["cost_of_goods_sold"] == 100000.0

    # Cost changes AFTER the sale — a naive "join current Product.cost_price"
    # implementation would silently inflate the already-reported COGS.
    row = (await db_session.execute(select(Product).where(Product.id == product.id))).scalar_one()
    row.cost_price = Decimal("999999")
    db_session.add(row)
    await db_session.flush()

    after_cost_change = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert after_cost_change["summary"]["cost_of_goods_sold"] == 100000.0
    assert after_cost_change["summary"]["gross_profit"] == original["summary"]["gross_profit"]


# ─── Profit sign / margin null-handling ────────────────────────────────────

async def test_negative_profit_when_sold_below_cost(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("50000"), Decimal("40000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    await _sell(client, cashier, product, qty=1)

    resp = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert resp["summary"]["gross_profit"] == -10000.0
    assert resp["summary"]["status"] == "loss"


async def test_zero_revenue_period_has_null_margin_not_crash(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")

    resp = await _pl(client, admin, period="custom", from_date="2020-01-01", to_date="2020-01-01", branch_id=str(branch.id))
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["revenue"] == 0.0
    assert summary["gross_margin"] is None
    assert summary["net_margin"] is None
    assert summary["status"] == "break_even"


# ─── Operating expenses: shortage counts, surplus does not ────────────────

async def test_shortage_day_expense_counted_as_operating_expense(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("10000"), Decimal("100000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    await _sell(client, cashier, product, qty=1, payment_method="cash")  # system cash = 100000

    close_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={
            "branch_id": str(branch.id),
            "counted_cash": "90000",  # 10,000 shortage
            "expenses": [{"description": "Usafiri (transport)", "amount": "10000"}],
        },
    )
    assert close_resp.status_code == 201

    resp = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert resp["summary"]["operating_expenses"] == 10000.0
    assert resp["summary"]["net_profit"] == resp["summary"]["gross_profit"] - 10000.0


async def test_surplus_day_expense_excluded_from_operating_expense(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("10000"), Decimal("100000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    await _sell(client, cashier, product, qty=1, payment_method="cash")  # system cash = 100000

    close_resp = await client.post(
        "/api/v1/closings/close",
        headers=auth_headers(admin),
        json={
            "branch_id": str(branch.id),
            "counted_cash": "105000",  # 5,000 surplus — the "matumizi" note explains it, isn't a real expense
            "expenses": [{"description": "Unclaimed customer change", "amount": "5000"}],
        },
    )
    assert close_resp.status_code == 201

    resp = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert resp["summary"]["operating_expenses"] == 0.0
    assert resp["summary"]["net_profit"] == resp["summary"]["gross_profit"]


async def test_no_expenses_defaults_to_zero(client, db_session):
    branch = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    resp = (await _pl(client, admin, period="today", branch_id=str(branch.id))).json()
    assert resp["summary"]["operating_expenses"] == 0.0


# ─── Date boundaries: 23:59 / 00:00 / 00:01 Tanzania ───────────────────────

async def test_business_date_boundary_2359_attributed_to_earlier_day(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("1000"), Decimal("2000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _sell(client, cashier, product, qty=1)
    # Tanzania is UTC+3 with no DST: local 23:59 on the 14th == UTC 20:59 on the 14th.
    await db_session.execute(
        update(Sale).where(Sale.id == sale["id"]).values(created_at=datetime(2026, 6, 14, 20, 59, 0))
    )
    await db_session.flush()

    on_14th = (await _pl(client, admin, period="custom", from_date="2026-06-14", to_date="2026-06-14", branch_id=str(branch.id))).json()
    on_15th = (await _pl(client, admin, period="custom", from_date="2026-06-15", to_date="2026-06-15", branch_id=str(branch.id))).json()
    assert on_14th["summary"]["revenue"] == 2000.0
    assert on_15th["summary"]["revenue"] == 0.0


async def test_business_date_boundary_0000_attributed_to_next_day(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("1000"), Decimal("2000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _sell(client, cashier, product, qty=1)
    # local 00:00 on the 15th == UTC 21:00 on the 14th.
    await db_session.execute(
        update(Sale).where(Sale.id == sale["id"]).values(created_at=datetime(2026, 6, 14, 21, 0, 0))
    )
    await db_session.flush()

    on_14th = (await _pl(client, admin, period="custom", from_date="2026-06-14", to_date="2026-06-14", branch_id=str(branch.id))).json()
    on_15th = (await _pl(client, admin, period="custom", from_date="2026-06-15", to_date="2026-06-15", branch_id=str(branch.id))).json()
    assert on_14th["summary"]["revenue"] == 0.0
    assert on_15th["summary"]["revenue"] == 2000.0


async def test_business_date_boundary_0001_attributed_to_next_day(client, db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("1000"), Decimal("2000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch, quantity=10)

    sale = await _sell(client, cashier, product, qty=1)
    # local 00:01 on the 15th == UTC 21:01 on the 14th.
    await db_session.execute(
        update(Sale).where(Sale.id == sale["id"]).values(created_at=datetime(2026, 6, 14, 21, 1, 0))
    )
    await db_session.flush()

    on_15th = (await _pl(client, admin, period="custom", from_date="2026-06-15", to_date="2026-06-15", branch_id=str(branch.id))).json()
    assert on_15th["summary"]["revenue"] == 2000.0


# ─── Branch breakdown reconciles to summary ────────────────────────────────

async def test_all_branches_breakdown_sums_to_summary(client, db_session):
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier_a = await make_user(db_session, "cashier", branch=branch_a)
    cashier_b = await make_user(db_session, "cashier", branch=branch_b)
    admin = await make_user(db_session, "admin")
    product = await make_product(db_session)
    product.cost_price, product.selling_price = Decimal("10000"), Decimal("20000")
    db_session.add(product)
    await db_session.flush()
    await make_inventory(db_session, product, branch_a, quantity=10)
    await make_inventory(db_session, product, branch_b, quantity=10)

    await _sell(client, cashier_a, product, qty=1)
    await _sell(client, cashier_b, product, qty=2)

    # No branch_id => consolidated ALL view (global role, branch_context allows it).
    resp = (await _pl(client, admin, period="today")).json()
    branch_rows = {b["branch_id"]: b for b in resp["branches"]}
    assert branch_rows[str(branch_a.id)]["revenue"] == 20000.0
    assert branch_rows[str(branch_b.id)]["revenue"] == 40000.0
