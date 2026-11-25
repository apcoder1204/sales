"""Authorized reversal of a debt payment (spec §6.3 Payment reversal)."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.customer_ledger import CustomerLedgerEntry
from app.services import ledger_service
from tests.conftest import auth_headers, make_user
from tests.test_debt_payments import World


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


async def _reverse(w, user, pid, reason="Imerekodiwa kimakosa", key=None):
    headers = auth_headers(user)
    if key:
        headers["Idempotency-Key"] = key
    return await w.client.post(f"/api/v1/payments/{pid}/reverse", json={"reason": reason}, headers=headers)


@pytest.mark.asyncio
async def test_reverse_restores_receivable(w):
    sale = await w.credit_sale(w.b, w.cashier_b, 4)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})
    pid = r.json()["id"]
    assert (await w.receivables(w.cashier_b))[str(sale)]["outstanding"] == "300000.00"

    rv = await _reverse(w, w.admin, pid)
    assert rv.status_code == 200, rv.text
    assert rv.json()["status"] == "reversed"
    assert rv.json()["reversal_reason"] == "Imerekodiwa kimakosa"
    assert (await w.receivables(w.cashier_b))[str(sale)]["outstanding"] == "400000.00"
    assert await ledger_service.customer_balance(w.db, w.customer.id) == Decimal("400000")

    listed = await w.client.get(f"/api/v1/customers/{w.customer.id}/payments", headers=auth_headers(w.admin))
    assert [p["status"] for p in listed.json()] == ["reversed"]
    rows = (await w.db.execute(select(CustomerLedgerEntry).where(
        CustomerLedgerEntry.source_type == "payment", CustomerLedgerEntry.source_id == listed.json()[0]["id"]
    ))).scalars().all()
    by_type = {r.entry_type: r for r in rows}
    assert set(by_type) == {"payment", "payment_reversal"}
    assert by_type["payment_reversal"].debit == Decimal("100000")
    assert by_type["payment_reversal"].reverses_entry_id == by_type["payment"].id

    rec = await w.client.get(f"/api/v1/payments/{pid}/receipt", headers=auth_headers(w.cashier_b))
    assert rec.json()["reversed"] is True


@pytest.mark.asyncio
async def test_double_reverse_rejected(w):
    await w.credit_sale(w.b, w.cashier_b, 4)
    pid = (await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})).json()["id"]
    assert (await _reverse(w, w.admin, pid)).status_code == 200
    again = await _reverse(w, w.admin, pid)
    assert again.status_code == 400
    assert again.json()["code"] == "PAYMENT_ALREADY_REVERSED"


@pytest.mark.asyncio
async def test_idempotent_reverse_retry(w):
    await w.credit_sale(w.b, w.cashier_b, 4)
    pid = (await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})).json()["id"]
    r1 = await _reverse(w, w.admin, pid, key="rev-1")
    r2 = await _reverse(w, w.admin, pid, key="rev-1")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


@pytest.mark.asyncio
async def test_sale_payment_cannot_be_reversed_directly(w):
    r = await w.client.post("/api/v1/sales", json={
        "branch_id": str(w.b.id), "customer_id": str(w.customer.id),
        "payments": [{"method": "cash", "amount": "50000"}],
        "items": [{"product_id": str(w.product.id), "quantity": 1}],
    }, headers=auth_headers(w.cashier_b))
    pid = r.json()["sale"]["payments"][0]["id"]
    rv = await _reverse(w, w.admin, pid)
    assert rv.status_code == 400
    assert rv.json()["code"] == "SALE_PAYMENT_USE_VOID"


@pytest.mark.asyncio
async def test_cashier_cannot_reverse(w):
    await w.credit_sale(w.b, w.cashier_b, 4)
    pid = (await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})).json()["id"]
    assert (await _reverse(w, w.cashier_b, pid)).status_code == 403


@pytest.mark.asyncio
async def test_general_manager_cannot_reverse(w):
    gm = await make_user(w.db, "general_manager")
    await w.credit_sale(w.b, w.cashier_b, 4)
    pid = (await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})).json()["id"]
    assert (await _reverse(w, gm, pid)).status_code == 403


@pytest.mark.asyncio
async def test_reverse_requires_reason(w):
    await w.credit_sale(w.b, w.cashier_b, 4)
    pid = (await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})).json()["id"]
    assert (await _reverse(w, w.admin, pid, reason="no")).status_code == 422


@pytest.mark.asyncio
async def test_reverse_blocked_on_closed_day(w):
    await w.credit_sale(w.b, w.cashier_b, 4)
    pid = (await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})).json()["id"]
    c = await w.client.post("/api/v1/closings/close", json={"branch_id": str(w.b.id)},
                            headers=auth_headers(w.cashier_b))
    assert c.status_code == 201, c.text
    rv = await _reverse(w, w.admin, pid)
    assert rv.status_code == 400
    assert rv.json()["code"] == "DAY_ALREADY_CLOSED"
