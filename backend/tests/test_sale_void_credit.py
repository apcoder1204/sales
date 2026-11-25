"""Voiding a sale undoes its payments and the customer's debt (spec §6.3 Sale void)."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.business_time import business_date_today
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.payment import Payment, PaymentAllocation
from app.services import ledger_service
from tests.conftest import (
    auth_headers, make_branch, make_customer, make_inventory, make_product, make_user,
)


async def _setup(db):
    branch = await make_branch(db)
    cashier = await make_user(db, "cashier", branch=branch)
    admin = await make_user(db, "admin")
    product = await make_product(db)
    product.selling_price = Decimal("80000")
    product.cost_price = Decimal("50000")
    await db.flush()
    await make_inventory(db, product, branch, quantity=100)
    return branch, cashier, admin, product


async def _sell(client, cashier, branch, product, payments, customer=None):
    body = {"branch_id": str(branch.id), "payments": payments,
            "items": [{"product_id": str(product.id), "quantity": 5}]}
    if customer:
        body["customer_id"] = str(customer.id)
    r = await client.post("/api/v1/sales", json=body, headers=auth_headers(cashier))
    assert r.status_code == 201, r.text
    return r.json()["sale"]


async def _void(client, admin, sale_id):
    return await client.post(f"/api/v1/sales/{sale_id}/void", json={"reason": "Kosa la mauzo"},
                             headers=auth_headers(admin))


@pytest.mark.asyncio
async def test_void_credit_sale_restores_balance(client, db_session):
    branch, cashier, admin, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"))
    sale = await _sell(client, cashier, branch, product, [{"method": "cash", "amount": "150000"}], customer)
    assert await ledger_service.customer_balance(db_session, customer.id) == Decimal("250000")

    r = await _void(client, admin, sale["id"])
    assert r.status_code == 200, r.text
    assert await ledger_service.customer_balance(db_session, customer.id) == Decimal("0")

    pay = (await db_session.execute(select(Payment).where(Payment.id == uuid.UUID(sale["payments"][0]["id"])))).scalar_one()
    await db_session.refresh(pay)
    assert pay.status == "reversed"
    assert pay.reversed_by == admin.id
    assert pay.reversal_reason.endswith("Kosa la mauzo")

    rows = (await db_session.execute(select(CustomerLedgerEntry).where(
        CustomerLedgerEntry.customer_id == customer.id
    ))).scalars().all()
    kinds = sorted((r.entry_type, r.debit, r.credit) for r in rows)
    assert kinds == [
        ("payment", Decimal("0.00"), Decimal("150000.00")),
        ("payment_reversal", Decimal("150000.00"), Decimal("0.00")),
        ("sale", Decimal("400000.00"), Decimal("0.00")),
        ("sale_void", Decimal("0.00"), Decimal("400000.00")),
    ]
    by_type = {r.entry_type: r for r in rows}
    assert by_type["sale_void"].reverses_entry_id == by_type["sale"].id
    assert by_type["payment_reversal"].reverses_entry_id == by_type["payment"].id
    assert await ledger_service.receivables(db_session, customer.id) == []


@pytest.mark.asyncio
async def test_void_walk_in_sale_reverses_payments(client, db_session):
    branch, cashier, admin, product = await _setup(db_session)
    keep = await _sell(client, cashier, branch, product, [{"method": "cash", "amount": "400000"}])
    gone = await _sell(client, cashier, branch, product, [{"method": "cash", "amount": "400000"}])
    r = await _void(client, admin, gone["id"])
    assert r.status_code == 200, r.text
    pay = (await db_session.execute(select(Payment).where(Payment.id == uuid.UUID(gone["payments"][0]["id"])))).scalar_one()
    await db_session.refresh(pay)
    assert pay.status == "reversed"
    prev = await client.get("/api/v1/closings/preview", params={"branch_id": str(branch.id)},
                            headers=auth_headers(admin))
    assert prev.status_code == 200, prev.text
    assert prev.json()["total_cash"] == 400000
    assert keep["id"]
    got = await client.get(f"/api/v1/sales/{gone['id']}", headers=auth_headers(admin))
    assert got.json()["payment_status"] == "VOIDED"
    assert got.json()["payment_method"] == "cash"


@pytest.mark.asyncio
async def test_void_blocked_by_debt_payment(client, db_session):
    branch, cashier, admin, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"))
    sale = await _sell(client, cashier, branch, product, [], customer)
    debt_pay = Payment(
        payment_no=f"PAY-T-{uuid.uuid4().hex[:8]}", kind="debt", customer_id=customer.id,
        branch_id=branch.id, method="cash", amount=Decimal("100000"),
        business_date=business_date_today(), received_by=cashier.id, status="active",
    )
    db_session.add(debt_pay)
    await db_session.flush()
    db_session.add(PaymentAllocation(payment_id=debt_pay.id, sale_id=uuid.UUID(sale["id"]),
                                     amount=Decimal("100000")))
    await db_session.flush()

    r = await _void(client, admin, sale["id"])
    assert r.status_code == 400
    assert r.json()["code"] == "SALE_HAS_DEBT_PAYMENTS"
    got = await client.get(f"/api/v1/sales/{sale['id']}", headers=auth_headers(admin))
    assert got.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_void_allowed_after_debt_payment_reversed(client, db_session):
    branch, cashier, admin, product = await _setup(db_session)
    customer = await make_customer(db_session, credit_limit=Decimal("2000000"))
    sale = await _sell(client, cashier, branch, product, [], customer)
    debt_pay = Payment(
        payment_no=f"PAY-T-{uuid.uuid4().hex[:8]}", kind="debt", customer_id=customer.id,
        branch_id=branch.id, method="cash", amount=Decimal("100000"),
        business_date=business_date_today(), received_by=cashier.id, status="reversed",
    )
    db_session.add(debt_pay)
    await db_session.flush()
    db_session.add(PaymentAllocation(payment_id=debt_pay.id, sale_id=uuid.UUID(sale["id"]),
                                     amount=Decimal("100000")))
    await db_session.flush()
    r = await _void(client, admin, sale["id"])
    assert r.status_code == 200, r.text
    assert await ledger_service.customer_balance(db_session, customer.id) == Decimal("0")
