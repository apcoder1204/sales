"""Factual credit-risk indicators (brief §15): figures and flags, never a
"bad debtor" label."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.core.business_time import business_date_today
from tests.conftest import auth_headers, make_customer
from tests.test_debt_payments import World

D = Decimal


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


async def detail(w, customer=None, user=None):
    r = await w.client.get(f"/api/v1/customers/{(customer or w.customer).id}",
                           headers=auth_headers(user or w.admin))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_flags_near_and_over_limit(w):
    w.customer.credit_limit = D("1000000")
    await w.db.flush()
    await w.credit_sale(w.a, w.cashier_a, 8, due_in_days=10)
    assert (await detail(w))["summary"]["flags"] == ["NEAR_LIMIT"]
    w.customer.credit_limit = D("700000")
    await w.db.flush()
    assert (await detail(w))["summary"]["flags"] == ["OVER_LIMIT"]


@pytest.mark.asyncio
async def test_flags_overdue_and_long_outstanding(w):
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=-10)
    assert (await detail(w))["summary"]["flags"] == ["OVERDUE"]
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=-100)
    assert (await detail(w))["summary"]["flags"] == ["OVERDUE", "LONG_OUTSTANDING"]


@pytest.mark.asyncio
async def test_flags_inactive_with_debt(w):
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=10)
    w.customer.status = "inactive"
    await w.db.flush()
    assert (await detail(w))["summary"]["flags"] == ["INACTIVE_WITH_DEBT"]


@pytest.mark.asyncio
async def test_no_flags_for_clean_customer(w):
    clean = await make_customer(w.db, credit_limit=D("500000"))
    body = await detail(w, clean)
    assert body["summary"]["flags"] == []
    assert body["risk"]["overdue_count"] == 0 and body["risk"]["oldest_open_date"] is None
    assert D(body["risk"]["limit_used_pct"]) == 0


@pytest.mark.asyncio
async def test_detail_risk_details(w):
    r = await w.client.post("/api/v1/sales", json={
        "branch_id": str(w.a.id), "customer_id": str(w.customer.id),
        "payments": [{"method": "cash", "amount": "150000"}],
        "items": [{"product_id": str(w.product.id), "quantity": 3}],
    }, headers=auth_headers(w.cashier_a))
    assert r.status_code == 201, r.text
    risk = (await detail(w))["risk"]
    assert D(risk["total_purchases"]) == D(300000)
    assert D(risk["total_payments"]) == D(150000)
    assert risk["oldest_open_date"] == business_date_today().isoformat()
    assert D(risk["limit_used_pct"]) == D("3.00")  # 150,000 of 5,000,000
    plain = await make_customer(w.db)
    assert (await detail(w, plain))["risk"]["limit_used_pct"] is None  # no limit set


@pytest.mark.asyncio
async def test_overdue_count(w):
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=-3)
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=-30)
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=5)
    assert (await detail(w))["risk"]["overdue_count"] == 2


@pytest.mark.asyncio
async def test_list_carries_flags_without_extra_queries(w, db_session):
    tag = uuid.uuid4().hex[:6]
    for i in range(3):
        c = await make_customer(w.db, name=f"Risk Count {tag} {i}", credit_limit=D("1000000"))
        w.customer = c
        await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=-5)
        c.credit_limit = D("1000")  # limit lowered after the sale → over limit
    await w.db.flush()

    count = {"n": 0}

    def on_exec(*_a, **_k):
        count["n"] += 1

    engine = db_session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", on_exec)
    try:
        async def queries(q):
            count["n"] = 0
            r = await w.client.get("/api/v1/customers", params={"q": q}, headers=auth_headers(w.admin))
            assert r.status_code == 200, r.text
            return count["n"], r.json()["items"]
        one, _ = await queries(f"Risk Count {tag} 0")
        three, items = await queries(f"Risk Count {tag}")
    finally:
        event.remove(engine, "before_cursor_execute", on_exec)
    assert len(items) == 3
    assert all(set(x["flags"]) == {"OVER_LIMIT", "OVERDUE"} for x in items)
    per_customer = (three - one) / 2
    # 13 = what stage 1 already spent per row (measured on the pre-flags code,
    # including the selectin loads behind receivables); flags must add none.
    assert per_customer <= 13, per_customer


@pytest.mark.asyncio
async def test_cashier_never_sees_all_branch_limit_use(w):
    """A cashier at branch B must not learn branch A's debt: over the limit,
    the % used would reveal the all-branch balance (D4: cashiers see only
    the available credit)."""
    w.customer.credit_limit = D("1000000")
    await w.db.flush()
    await w.credit_sale(w.a, w.cashier_a, 9)          # A owes 900k
    await w.credit_sale(w.b, w.cashier_b, 1)          # B owes 100k
    w.customer.credit_limit = D("500000")             # now 200% used overall
    await w.db.flush()
    cashier_view = await detail(w, user=w.cashier_b)
    assert cashier_view["risk"]["limit_used_pct"] is None
    assert D(cashier_view["summary"]["balance"]) == D(100000)
    admin_view = await detail(w)
    assert D(admin_view["risk"]["limit_used_pct"]) == D("200.00")
