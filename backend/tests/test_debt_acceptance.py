"""Acceptance scenario (brief §33 / spec §12), stages 1 and 2: ABC Technologies buys
5 items at 80,000 (cost 50,000), pays 150,000 cash, owes 250,000."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.customer_ledger import CustomerLedgerEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.services import ledger_service
from tests.conftest import (
    auth_headers, make_branch, make_customer, make_inventory, make_product, make_user,
)


@pytest.mark.asyncio
async def test_abc_technologies_scenario(client, db_session):
    db = db_session
    branch = await make_branch(db)
    other = await make_branch(db)
    cashier = await make_user(db, "cashier", branch=branch)
    other_cashier = await make_user(db, "cashier", branch=other)
    admin = await make_user(db, "admin")
    product = await make_product(db)
    product.cost_price = Decimal("50000")
    product.selling_price = Decimal("80000")
    await db.flush()
    await make_inventory(db, product, branch, quantity=20)
    abc = await make_customer(db, name="ABC Technologies", customer_type="business",
                              credit_limit=Decimal("2000000"))

    r = await client.post("/api/v1/sales", json={
        "branch_id": str(branch.id), "customer_id": str(abc.id),
        "payments": [{"method": "cash", "amount": "150000"}],
        "items": [{"product_id": str(product.id), "quantity": 5}],
    }, headers=auth_headers(cashier))
    assert r.status_code == 201, r.text
    sale = r.json()["sale"]
    sale_id = uuid.UUID(sale["id"])

    # 1. exactly one sale; 2. linked to ABC
    n_sales = (await db.execute(select(func.count()).select_from(Sale).where(Sale.branch_id == branch.id))).scalar()
    assert n_sales == 1
    assert sale["customer"]["id"] == str(abc.id)

    # 3-5. P&L: revenue 400,000, COGS 250,000, gross profit 150,000
    async def pl():
        res = await client.get("/api/v1/reports/profit-loss", params={"period": "today", "branch_id": str(branch.id)},
                               headers=auth_headers(admin))
        assert res.status_code == 200, res.text
        s = res.json()["summary"]
        return s["revenue"], s["cost_of_goods_sold"], s["gross_profit"]
    assert await pl() == (400000, 250000, 150000)

    # 6-7. one sale payment of 150,000 allocated to the sale
    sale_payments = (await db.execute(
        select(Payment).join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .where(PaymentAllocation.sale_id == sale_id)
    )).scalars().all()
    assert [(p.kind, p.amount, p.method) for p in sale_payments] == [("sale", Decimal("150000.00"), "cash")]

    # 8. balance 250,000
    assert await ledger_service.customer_balance(db, abc.id) == Decimal("250000")

    # 12. closing: cash includes 150,000; credit given 250,000
    prev = await client.get("/api/v1/closings/preview", params={"branch_id": str(branch.id)},
                            headers=auth_headers(admin))
    assert prev.json()["total_cash"] == 150000
    assert prev.json()["total_credit_given"] == 250000
    assert prev.json()["total_revenue"] == 400000

    # Debt payment 100,000 → balance 150,000; 11. P&L unchanged
    pay = await client.post(f"/api/v1/customers/{abc.id}/payments",
                            json={"method": "cash", "amount": "100000"}, headers=auth_headers(cashier))
    assert pay.status_code == 201, pay.text
    assert await ledger_service.customer_balance(db, abc.id) == Decimal("150000")
    assert await pl() == (400000, 250000, 150000)

    # Reverse it → balance back to 250,000; both payments still listed
    rv = await client.post(f"/api/v1/payments/{pay.json()['id']}/reverse",
                           json={"reason": "Imerekodiwa kimakosa"}, headers=auth_headers(admin))
    assert rv.status_code == 200, rv.text
    assert await ledger_service.customer_balance(db, abc.id) == Decimal("250000")
    listed = await client.get(f"/api/v1/customers/{abc.id}/payments", headers=auth_headers(admin))
    rows = {(p["kind"], p["amount"], p["status"]) for p in listed.json()}
    assert rows == {("debt", "100000.00", "reversed"), ("sale", "150000.00", "active")}

    ledger = (await db.execute(select(CustomerLedgerEntry).where(CustomerLedgerEntry.customer_id == abc.id))).scalars().all()
    assert sorted((e.entry_type, e.debit, e.credit) for e in ledger) == [
        ("payment", Decimal("0.00"), Decimal("100000.00")),
        ("payment", Decimal("0.00"), Decimal("150000.00")),
        ("payment_reversal", Decimal("100000.00"), Decimal("0.00")),
        ("sale", Decimal("400000.00"), Decimal("0.00")),
    ]

    # Stage 2: the statement tells the same story and ends at the balance
    st = await client.get(f"/api/v1/customers/{abc.id}/statement", headers=auth_headers(admin))
    assert st.status_code == 200, st.text
    st = st.json()
    assert [(x["entry_type"], Decimal(x["debit"]), Decimal(x["credit"])) for x in st["lines"]] == [
        ("sale", Decimal("400000"), 0), ("payment", 0, Decimal("150000")),
        ("payment", 0, Decimal("100000")), ("payment_reversal", Decimal("100000"), 0),
    ]
    assert Decimal(st["closing_balance"]) == Decimal("250000") == await ledger_service.customer_balance(db, abc.id)
    # ageing: due in 30 days → not yet due; the outstanding report agrees
    ag = (await client.get("/api/v1/reports/debts/ageing", params={"branch_id": str(branch.id)},
                           headers=auth_headers(admin))).json()
    [abc_row] = [r for r in ag["rows"] if r["customer"]["id"] == str(abc.id)]
    assert Decimal(abc_row["buckets"]["not_due"]) == Decimal("250000") == Decimal(abc_row["total"])
    out = (await client.get("/api/v1/reports/debts/outstanding", params={"branch_id": str(branch.id)},
                            headers=auth_headers(admin))).json()
    [abc_out] = [r for r in out["rows"] if r["customer"]["id"] == str(abc.id)]
    assert Decimal(abc_out["balance"]) == Decimal("250000")

    # A cashier at another branch: no receivables, no sale, can't pay it
    h = auth_headers(other_cashier)
    rec = await client.get(f"/api/v1/customers/{abc.id}/receivables", headers=h)
    assert rec.status_code == 200 and rec.json() == []
    assert (await client.get(f"/api/v1/sales/{sale_id}", headers=h)).status_code == 404
    bad = await client.post(f"/api/v1/customers/{abc.id}/payments", json={
        "method": "cash", "amount": "50000", "allocations": [{"sale_id": str(sale_id), "amount": "50000"}],
    }, headers=h)
    assert bad.status_code == 400
    assert bad.json()["code"] == "ALLOCATION_INVALID"
