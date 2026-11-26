"""Customer statement (brief §13): opening balance, ledger lines with a
running balance, closing balance — always equal to the ledger."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text, update

from app.core.business_time import business_date_today
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.sale import Sale
from app.services import ledger_service
from tests.conftest import auth_headers, make_user
from tests.test_debt_payments import World

D = Decimal


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


async def statement(w, user, **params):
    r = await w.client.get(f"/api/v1/customers/{w.customer.id}/statement",
                           params={k: str(v) for k, v in params.items()}, headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


def lines(body):
    return [(x["entry_type"], D(x["debit"]), D(x["credit"]), D(x["balance"])) for x in body["lines"]]


async def backdate(w, source_id, entry_type, days_ago):
    await w.db.execute(text("SET LOCAL dukani.ledger_maintenance = 'on'"))
    await w.db.execute(update(CustomerLedgerEntry).where(
        CustomerLedgerEntry.source_id == source_id, CustomerLedgerEntry.entry_type == entry_type,
    ).values(business_date=business_date_today() - timedelta(days=days_ago)))
    await w.db.flush()


@pytest.mark.asyncio
async def test_statement_lines_and_running_balance(w):
    sale_id = await w.credit_sale(w.a, w.cashier_a, 2)
    r = await w.pay(w.cashier_a, {"method": "cash", "amount": "50000"})
    assert r.status_code == 201, r.text
    body = await statement(w, w.admin)
    sale = await w.db.get(Sale, sale_id)
    assert lines(body) == [("sale", D(200000), D(0), D(200000)), ("payment", D(0), D(50000), D(150000))]
    assert D(body["opening_balance"]) == 0
    assert D(body["closing_balance"]) == D(150000)
    assert (D(body["total_debit"]), D(body["total_credit"])) == (D(200000), D(50000))
    assert D(body["closing_balance"]) == await ledger_service.customer_balance(w.db, w.customer.id)
    assert body["lines"][0]["reference"] == sale.transaction_no
    assert body["lines"][1]["reference"] == r.json()["payment_no"]
    assert body["lines"][0]["branch_name"] == w.a.name


@pytest.mark.asyncio
async def test_statement_opening_balance_before_range(w):
    sale_id = await w.credit_sale(w.a, w.cashier_a, 2)
    await backdate(w, sale_id, "sale", 40)
    await w.pay(w.cashier_a, {"method": "cash", "amount": "50000"})
    body = await statement(w, w.admin, date_from=business_date_today())
    assert D(body["opening_balance"]) == D(200000)
    assert lines(body) == [("payment", D(0), D(50000), D(150000))]
    assert D(body["closing_balance"]) == D(150000)


@pytest.mark.asyncio
async def test_statement_range_cuts_through_reversal(w):
    sale_id = await w.credit_sale(w.a, w.cashier_a, 2)
    pay = await w.pay(w.cashier_a, {"method": "cash", "amount": "50000"})
    rv = await w.client.post(f"/api/v1/payments/{pay.json()['id']}/reverse",
                             json={"reason": "Imerekodiwa kimakosa"}, headers=auth_headers(w.admin))
    assert rv.status_code == 200, rv.text
    import uuid
    pay_id = uuid.UUID(pay.json()["id"])
    await backdate(w, sale_id, "sale", 5)
    await backdate(w, pay_id, "payment", 3)
    await backdate(w, pay_id, "payment_reversal", 1)
    today = business_date_today()
    body = await statement(w, w.admin, date_from=today - timedelta(days=2), date_to=today)
    assert D(body["opening_balance"]) == D(150000)
    assert lines(body) == [("payment_reversal", D(50000), D(0), D(200000))]
    assert D(body["closing_balance"]) == await ledger_service.customer_balance(w.db, w.customer.id)
    # a range ending before the reversal stops at the ledger balance on that day
    earlier = await statement(w, w.admin, date_from=today - timedelta(days=10), date_to=today - timedelta(days=2))
    assert D(earlier["closing_balance"]) == D(150000)


@pytest.mark.asyncio
async def test_statement_includes_void_and_old_debt(w):
    sale_id = await w.credit_sale(w.a, w.cashier_a, 1)
    v = await w.client.post(f"/api/v1/sales/{sale_id}/void", json={"reason": "Mteja amerudisha"},
                            headers=auth_headers(w.admin))
    assert v.status_code == 200, v.text
    ob = await w.client.post(f"/api/v1/customers/{w.customer.id}/opening-balances", json={
        "branch_id": str(w.a.id), "amount": "70000", "reference": "Daftari uk. 3",
        "effective_date": business_date_today().isoformat(),
    }, headers=auth_headers(w.admin))
    await w.client.post(f"/api/v1/opening-balances/{ob.json()['id']}/approve", json={}, headers=auth_headers(w.admin))
    body = await statement(w, w.admin)
    kinds = [(x["entry_type"], D(x["debit"]), D(x["credit"])) for x in body["lines"]]
    assert ("sale", D(100000), D(0)) in kinds and ("sale_void", D(0), D(100000)) in kinds
    old = next(x for x in body["lines"] if x["entry_type"] == "opening_balance")
    assert old["reference"].startswith("DENI-ZAMANI") and D(old["debit"]) == D(70000)
    assert D(body["closing_balance"]) == D(70000)


@pytest.mark.asyncio
async def test_cashier_statement_only_own_branch(w):
    await w.credit_sale(w.a, w.cashier_a, 2)
    await w.credit_sale(w.b, w.cashier_b, 1)
    body = await statement(w, w.cashier_b, branch_id=w.a.id)
    assert {x["branch_name"] for x in body["lines"]} == {w.b.name}
    assert D(body["closing_balance"]) == D(100000)
    assert body["branch_id"] == str(w.b.id)
    admin_a = await statement(w, w.admin, branch_id=w.a.id)
    assert D(admin_a["closing_balance"]) == D(200000)
    everything = await statement(w, w.admin)
    assert D(everything["closing_balance"]) == D(300000)


@pytest.mark.asyncio
async def test_statement_bad_range_and_roles(w):
    today = business_date_today()
    r = await w.client.get(f"/api/v1/customers/{w.customer.id}/statement",
                           params={"date_from": str(today), "date_to": str(today - timedelta(days=1))},
                           headers=auth_headers(w.admin))
    assert r.status_code == 422
    assert r.json()["code"] == "DATE_RANGE_INVALID"
    keeper = await make_user(w.db, "store_keeper")
    r = await w.client.get(f"/api/v1/customers/{w.customer.id}/statement", headers=auth_headers(keeper))
    assert r.status_code == 403
