"""Debt payments: FIFO/manual allocation, branch rules, receipts (spec §6.3)."""
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, update

from app.core.business_time import business_date_today
from app.models.payment import Payment
from app.models.sale import Sale
from app.services import ledger_service
from app.services.sale_service import _fmt
from tests.conftest import (
    auth_headers, make_branch, make_customer, make_inventory, make_product, make_user,
)


class World:
    """Two POS branches with a cashier each, one product priced 100,000."""

    def __init__(self, db, client):
        self.db, self.client = db, client

    async def build(self):
        db = self.db
        self.a = await make_branch(db)
        self.b = await make_branch(db)
        self.cashier_a = await make_user(db, "cashier", branch=self.a)
        self.cashier_b = await make_user(db, "cashier", branch=self.b)
        self.admin = await make_user(db, "admin")
        self.product = await make_product(db)
        self.product.selling_price = Decimal("100000")
        self.product.cost_price = Decimal("60000")
        await db.flush()
        await make_inventory(db, self.product, self.a, quantity=100)
        await make_inventory(db, self.product, self.b, quantity=100)
        self.customer = await make_customer(db, credit_limit=Decimal("5000000"))
        return self

    async def credit_sale(self, branch, cashier, qty, due_in_days=None):
        r = await self.client.post("/api/v1/sales", json={
            "branch_id": str(branch.id), "customer_id": str(self.customer.id), "payments": [],
            "items": [{"product_id": str(self.product.id), "quantity": qty}],
        }, headers=auth_headers(cashier))
        assert r.status_code == 201, r.text
        sale_id = uuid.UUID(r.json()["sale"]["id"])
        if due_in_days is not None:
            await self.db.execute(update(Sale).where(Sale.id == sale_id).values(
                due_date=business_date_today() + timedelta(days=due_in_days)
            ))
            await self.db.flush()
        return sale_id

    async def pay(self, user, body, key=None):
        headers = auth_headers(user)
        if key:
            headers["Idempotency-Key"] = key
        return await self.client.post(
            f"/api/v1/customers/{self.customer.id}/payments", json=body, headers=headers
        )

    async def receivables(self, user, **params):
        r = await self.client.get(f"/api/v1/customers/{self.customer.id}/receivables",
                                  params=params, headers=auth_headers(user))
        assert r.status_code == 200, r.text
        return {x["id"]: x for x in r.json()}

    async def debt_payment_count(self):
        return (await self.db.execute(select(func.count()).select_from(Payment).where(
            Payment.kind == "debt", Payment.customer_id == self.customer.id
        ))).scalar()


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


@pytest.mark.asyncio
async def test_cash_debt_payment_fifo(w):
    sale_a = await w.credit_sale(w.b, w.cashier_b, 3, due_in_days=10)
    sale_b = await w.credit_sale(w.b, w.cashier_b, 2, due_in_days=30)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "400000"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "debt" and body["payment_no"].startswith("PAY-")
    allocs = {a["receivable_id"]: a["amount"] for a in body["allocations"]}
    assert allocs == {str(sale_a): "300000.00", str(sale_b): "100000.00"}
    assert await ledger_service.customer_balance(w.db, w.customer.id) == Decimal("100000")

    rec = await w.client.get(f"/api/v1/payments/{body['id']}/receipt", headers=auth_headers(w.cashier_b))
    assert rec.status_code == 200, rec.text
    rb = rec.json()
    assert rb["balance_before"] == _fmt(Decimal("500000"))
    assert rb["balance_after"] == _fmt(Decimal("100000"))
    assert rb["customer_name"] == w.customer.name
    assert rb["reversed"] is False
    assert len(rb["allocations"]) == 2


@pytest.mark.asyncio
async def test_manual_allocation(w):
    sale_a = await w.credit_sale(w.b, w.cashier_b, 3, due_in_days=10)
    sale_b = await w.credit_sale(w.b, w.cashier_b, 2, due_in_days=30)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "150000", "allocations": [
        {"sale_id": str(sale_b), "amount": "150000"},
    ]})
    assert r.status_code == 201, r.text
    rows = await w.receivables(w.cashier_b)
    assert rows[str(sale_b)]["outstanding"] == "50000.00"
    assert rows[str(sale_a)]["outstanding"] == "300000.00"


@pytest.mark.asyncio
async def test_allocation_mismatch_rejected(w):
    sale_a = await w.credit_sale(w.b, w.cashier_b, 3)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "150000", "allocations": [
        {"sale_id": str(sale_a), "amount": "100000"},
    ]})
    assert r.status_code == 400
    assert r.json()["code"] == "ALLOCATION_MISMATCH"


@pytest.mark.asyncio
async def test_allocation_over_outstanding_rejected(w):
    sale_a = await w.credit_sale(w.b, w.cashier_b, 1)
    await w.credit_sale(w.b, w.cashier_b, 3)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "150000", "allocations": [
        {"sale_id": str(sale_a), "amount": "150000"},
    ]})
    assert r.status_code == 400
    assert r.json()["code"] == "ALLOCATION_INVALID"


@pytest.mark.asyncio
async def test_duplicate_allocation_target_rejected(w):
    sale_a = await w.credit_sale(w.b, w.cashier_b, 3)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "200000", "allocations": [
        {"sale_id": str(sale_a), "amount": "100000"},
        {"sale_id": str(sale_a), "amount": "100000"},
    ]})
    assert r.status_code == 400
    assert r.json()["code"] == "ALLOCATION_INVALID"


@pytest.mark.asyncio
async def test_payment_exceeds_debt_rejected(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "250000"})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "PAYMENT_EXCEEDS_DEBT"
    assert body["params"]["owed"] == "200000"


@pytest.mark.asyncio
async def test_mobile_money_requires_reference(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "mobile_money", "amount": "100000"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bank_payment_recorded_with_reference(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "bank_transfer", "amount": "100000", "reference": "CRDB-778"})
    assert r.status_code == 201, r.text
    assert r.json()["method"] == "bank_transfer"
    assert r.json()["reference"] == "CRDB-778"


@pytest.mark.asyncio
async def test_cashier_cannot_allocate_other_branch_sale(w):
    sale_at_a = await w.credit_sale(w.a, w.cashier_a, 2)
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "100000", "allocations": [
        {"sale_id": str(sale_at_a), "amount": "100000"},
    ]})
    assert r.status_code == 400
    assert r.json()["code"] == "ALLOCATION_INVALID"
    assert await w.debt_payment_count() == 0


@pytest.mark.asyncio
async def test_cashier_payment_forced_to_own_branch(w):
    await w.credit_sale(w.a, w.cashier_a, 2)
    sale_b = await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"branch_id": str(w.a.id), "method": "cash", "amount": "100000"})
    assert r.status_code == 201, r.text
    assert r.json()["branch_id"] == str(w.b.id)
    assert r.json()["allocations"][0]["receivable_id"] == str(sale_b)


@pytest.mark.asyncio
async def test_admin_must_name_branch(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.admin, {"method": "cash", "amount": "100000"})
    assert r.status_code == 400
    assert r.json()["code"] == "BRANCH_REQUIRED"
    r = await w.pay(w.admin, {"branch_id": str(w.b.id), "method": "cash", "amount": "100000"})
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_debt_payment_refused_when_day_closed(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    c = await w.client.post("/api/v1/closings/close", json={"branch_id": str(w.b.id)},
                            headers=auth_headers(w.cashier_b))
    assert c.status_code == 201, c.text
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "100000"})
    assert r.status_code == 400
    assert r.json()["code"] == "DAY_ALREADY_CLOSED"
    assert await w.debt_payment_count() == 0


@pytest.mark.asyncio
async def test_idempotent_retry_returns_same_payment(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    body = {"method": "cash", "amount": "50000"}
    r1 = await w.pay(w.cashier_b, body, key="retry-key-1")
    r2 = await w.pay(w.cashier_b, body, key="retry-key-1")
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["payment_no"] == r2.json()["payment_no"]
    assert await w.debt_payment_count() == 1


@pytest.mark.asyncio
async def test_receipt_reprint_has_no_side_effects(w):
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "50000"})
    pid = r.json()["id"]
    first = await w.client.get(f"/api/v1/payments/{pid}/receipt", headers=auth_headers(w.cashier_b))
    second = await w.client.get(f"/api/v1/payments/{pid}/receipt", headers=auth_headers(w.cashier_b))
    assert first.status_code == 200 and first.json() == second.json()
    assert await w.debt_payment_count() == 1


@pytest.mark.asyncio
async def test_cashier_cannot_view_other_branch_payment(w):
    await w.credit_sale(w.a, w.cashier_a, 2)
    r = await w.pay(w.cashier_a, {"method": "cash", "amount": "50000"})
    pid = r.json()["id"]
    for path in (f"/api/v1/payments/{pid}", f"/api/v1/payments/{pid}/receipt"):
        got = await w.client.get(path, headers=auth_headers(w.cashier_b))
        assert got.status_code == 404, path
    own = await w.client.get(f"/api/v1/payments/{pid}", headers=auth_headers(w.cashier_a))
    assert own.status_code == 200


@pytest.mark.asyncio
async def test_general_manager_cannot_record_payment(w):
    gm = await make_user(w.db, "general_manager")
    await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(gm, {"branch_id": str(w.b.id), "method": "cash", "amount": "50000"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_full_settlement_marks_paid(w):
    sale = await w.credit_sale(w.b, w.cashier_b, 2)
    r = await w.pay(w.cashier_b, {"method": "cash", "amount": "200000"})
    assert r.status_code == 201, r.text
    assert await w.receivables(w.cashier_b) == {}
    rows = await w.receivables(w.cashier_b, open_only="false")
    assert rows[str(sale)]["status"] == "PAID"
    assert rows[str(sale)]["outstanding"] == "0.00"


@pytest.mark.asyncio
async def test_cashier_reads_are_branch_scoped(w):
    sale_a = await w.credit_sale(w.a, w.cashier_a, 2)
    sale_b = await w.credit_sale(w.b, w.cashier_b, 1)
    await w.pay(w.cashier_a, {"method": "cash", "amount": "50000"})
    assert set(await w.receivables(w.cashier_b)) == {str(sale_b)}
    assert set(await w.receivables(w.admin)) == {str(sale_a), str(sale_b)}
    assert set(await w.receivables(w.admin, branch_id=str(w.a.id))) == {str(sale_a)}
    pays_b = await w.client.get(f"/api/v1/customers/{w.customer.id}/payments",
                                headers=auth_headers(w.cashier_b))
    assert pays_b.status_code == 200 and pays_b.json() == []
    pays_admin = await w.client.get(f"/api/v1/customers/{w.customer.id}/payments",
                                    headers=auth_headers(w.admin))
    assert len(pays_admin.json()) == 1
