"""Closing, dashboard and sales-report money figures come from payments; a
debt payment never adds revenue (spec §6.4)."""
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select

from app.db import seed_demo
from app.models.customer import Customer
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.payment import Payment
from app.models.stock_request import StockRequest
from app.models.stock_request_item import StockRequestItem
from app.models.stock_transfer import StockTransfer
from app.models.stock_transfer_item import StockTransferItem
from tests.conftest import auth_headers
from tests.test_debt_payments import World


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


async def _scenario(w):
    """Branch B, today: walk-in cash 100k; partial 400k with cash 150k;
    full credit 200k; then a 50k cash debt payment on the credit sale."""
    h = auth_headers(w.cashier_b)
    r = await w.client.post("/api/v1/sales", json={
        "branch_id": str(w.b.id), "payments": [{"method": "cash", "amount": "100000"}],
        "items": [{"product_id": str(w.product.id), "quantity": 1}],
    }, headers=h)
    assert r.status_code == 201, r.text
    r = await w.client.post("/api/v1/sales", json={
        "branch_id": str(w.b.id), "customer_id": str(w.customer.id),
        "payments": [{"method": "cash", "amount": "150000"}],
        "items": [{"product_id": str(w.product.id), "quantity": 4}],
    }, headers=h)
    assert r.status_code == 201, r.text
    credit_sale = await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "50000", "allocations": [
        {"sale_id": str(credit_sale), "amount": "50000"},
    ]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _preview(w):
    r = await w.client.get("/api/v1/closings/preview", params={"branch_id": str(w.b.id)},
                           headers=auth_headers(w.admin))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_closing_counts_collections_not_credit(w):
    await _scenario(w)
    p = await _preview(w)
    assert p["total_cash"] == 300000
    assert p["total_revenue"] == 700000
    assert p["total_sales_count"] == 3
    assert p["total_credit_given"] == 450000
    assert p["total_debt_collected"] == 50000


@pytest.mark.asyncio
async def test_close_stores_credit_and_collections(w):
    await _scenario(w)
    r = await w.client.post("/api/v1/closings/close", json={"branch_id": str(w.b.id)},
                            headers=auth_headers(w.cashier_b))
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["total_credit_given"]) == Decimal("450000")
    assert Decimal(body["total_debt_collected"]) == Decimal("50000")
    assert Decimal(body["total_cash"]) == Decimal("300000")


@pytest.mark.asyncio
async def test_reversed_debt_payment_excluded_from_closing(w):
    pid = await _scenario(w)
    rv = await w.client.post(f"/api/v1/payments/{pid}/reverse", json={"reason": "Kosa la kurekodi"},
                             headers=auth_headers(w.admin))
    assert rv.status_code == 200, rv.text
    p = await _preview(w)
    assert p["total_cash"] == 250000
    assert p["total_debt_collected"] == 0
    assert p["total_credit_given"] == 450000


@pytest.mark.asyncio
async def test_pl_unchanged_by_debt_payment(w):
    credit_sale = await w.credit_sale(w.b, w.cashier_b, 3)
    params = {"period": "today", "branch_id": str(w.b.id)}

    async def pl():
        r = await w.client.get("/api/v1/reports/profit-loss", params=params, headers=auth_headers(w.admin))
        assert r.status_code == 200, r.text
        s = r.json()["summary"]
        return s["revenue"], s["cost_of_goods_sold"], s["gross_profit"]

    before = await pl()
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "200000", "allocations": [
        {"sale_id": str(credit_sale), "amount": "200000"},
    ]})
    assert r.status_code == 201, r.text
    assert await pl() == before == (300000, 180000, 120000)


@pytest.mark.asyncio
async def test_dashboard_breakdown_has_credit(w):
    await _scenario(w)
    r = await w.client.get("/api/v1/reports/dashboard", params={"branch_id": str(w.b.id)},
                           headers=auth_headers(w.admin))
    assert r.status_code == 200, r.text
    b = r.json()["today_payment_breakdown"]
    assert b["credit"] == 450000
    assert b["cash"] == 250000  # sale-time only; the debt collection is not sales


@pytest.mark.asyncio
async def test_sales_report_breakdown_includes_credit_row(w):
    await _scenario(w)
    r = await w.client.get("/api/v1/reports/sales", params={"period": "today", "branch_id": str(w.b.id)},
                           headers=auth_headers(w.admin))
    assert r.status_code == 200, r.text
    rows = {x["method"]: x for x in r.json()["payment_breakdown"]}
    assert rows["Credit"] == {"method": "Credit", "count": 2, "total": 450000}
    assert rows["Cash"]["total"] == 250000 and rows["Cash"]["count"] == 2


@pytest.mark.asyncio
async def test_demo_wipe_handles_debt_tables(w, db_session):
    await _scenario(w)
    # Pre-existing gap, out of scope here: the demo wipe doesn't delete stock
    # requests, which reference products. Clear them (rolled back with the test).
    await db_session.execute(delete(StockTransferItem))
    await db_session.execute(delete(StockTransfer))
    await db_session.execute(delete(StockRequestItem))
    await db_session.execute(delete(StockRequest))
    await seed_demo._wipe_generated_data(db_session, commit=False)
    for model in (CustomerLedgerEntry, Payment, Customer):
        n = (await db_session.execute(select(func.count()).select_from(model))).scalar()
        assert n == 0, model.__name__
