"""Debt ageing (brief §14) and the debt dashboard (brief §18)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.core.business_time import utcnow
from app.models.sale import Sale
from app.services.debt_insights_service import ageing_bucket
from tests.conftest import auth_headers, make_customer
from tests.test_debt_payments import World

D = Decimal


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


async def get(w, user, path, **params):
    r = await w.client.get(f"/api/v1/receivables/{path}", params={k: str(v) for k, v in params.items()},
                           headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("days,bucket", [
    (0, "not_due"), (-5, "not_due"), (1, "1_30"), (30, "1_30"), (31, "31_60"),
    (60, "31_60"), (61, "61_90"), (90, "61_90"), (91, "90_plus"),
])
def test_ageing_bucket_edges(days, bucket):
    assert ageing_bucket(days) == bucket


@pytest.mark.asyncio
async def test_ageing_groups_per_customer_and_branch(w):
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=10)
    await w.credit_sale(w.a, w.cashier_a, 2, due_in_days=-20)
    await w.credit_sale(w.b, w.cashier_b, 3, due_in_days=-100)
    body = await get(w, w.admin, "ageing", branch_id=w.a.id)
    row = next(r for r in body["rows"] if r["customer"]["id"] == str(w.customer.id))
    assert {k: D(v) for k, v in row["buckets"].items()} == {
        "not_due": D(100000), "1_30": D(200000), "31_60": 0, "61_90": 0, "90_plus": 0}
    assert D(row["total"]) == D(300000)
    assert D(body["total"]) == sum(D(v) for v in body["totals"].values())
    assert [b["branch_name"] for b in body["by_branch"]] == [w.a.name]
    everything = await get(w, w.admin, "ageing")
    row = next(r for r in everything["rows"] if r["customer"]["id"] == str(w.customer.id))
    assert D(row["buckets"]["90_plus"]) == D(300000) and D(row["total"]) == D(600000)


@pytest.mark.asyncio
async def test_ageing_missing_due_date_uses_credit_days(w):
    sale_id = await w.credit_sale(w.a, w.cashier_a, 1)
    await w.db.execute(update(Sale).where(Sale.id == sale_id).values(
        due_date=None, created_at=utcnow() - timedelta(days=45)))
    await w.db.flush()
    body = await get(w, w.admin, "ageing", branch_id=w.a.id)
    row = next(r for r in body["rows"] if r["customer"]["id"] == str(w.customer.id))
    assert D(row["buckets"]["1_30"]) == D(100000)  # 45 days old, 30 credit days → 15 overdue


@pytest.mark.asyncio
async def test_dashboard_figures(w):
    other = await make_customer(w.db, name="Dash Other", credit_limit=D("5000000"))
    await w.credit_sale(w.a, w.cashier_a, 3, due_in_days=-40)       # oldest, overdue 300k
    sale2 = await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=5)
    w.customer, keep = other, w.customer
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=5)         # other customer 100k
    w.customer = keep
    pay = await w.pay(w.cashier_a, {"method": "cash", "amount": "50000",
                                    "allocations": [{"sale_id": str(sale2), "amount": "50000"}]})
    assert pay.status_code == 201, pay.text
    keep.credit_limit = D("100000")  # balance 350k is now over the limit
    await w.db.flush()
    body = await get(w, w.admin, "dashboard", branch_id=w.a.id, period="month")
    assert D(body["total_outstanding"]) == D(450000)
    assert body["customers_owing"] == 2
    assert D(body["overdue_total"]) == D(300000)
    assert D(body["collected_in_period"]) == D(50000)
    assert body["customers_over_limit"] == 1
    assert body["oldest_debt"]["customer"]["id"] == str(keep.id)
    assert body["oldest_debt"]["days_overdue"] == 40
    assert D(body["oldest_debt"]["outstanding"]) == D(300000)
    assert [t["customer"]["id"] for t in body["top_debtors"]] == [str(keep.id), str(other.id)]
    assert D(body["ageing"]["31_60"]) == D(300000) and D(body["ageing"]["not_due"]) == D(150000)


@pytest.mark.asyncio
async def test_dashboard_cashier_scope(w):
    await w.credit_sale(w.a, w.cashier_a, 2)
    await w.credit_sale(w.b, w.cashier_b, 1)
    body = await get(w, w.cashier_b, "dashboard", branch_id=w.a.id)
    mine = [t for t in body["top_debtors"] if t["customer"]["id"] == str(w.customer.id)]
    assert D(mine[0]["outstanding"]) == D(100000)
    ageing = await get(w, w.cashier_b, "ageing", branch_id=w.a.id)
    assert [b["branch_name"] for b in ageing["by_branch"]] == [w.b.name]
