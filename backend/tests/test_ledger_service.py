"""Ledger balances, receivables and derived receivable status (spec §6.1-6.3)."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.business_time import business_date_today
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.services import ledger_service
from tests.conftest import auth_headers, make_branch, make_customer, make_user

TODAY = date(2026, 11, 26)


@pytest.mark.parametrize(
    "amount,outstanding,due,expected",
    [
        (100, 0, None, "PAID"),
        (100, 100, TODAY + timedelta(days=5), "UNPAID"),
        (100, 40, TODAY + timedelta(days=5), "PARTIALLY_PAID"),
        (100, 40, TODAY - timedelta(days=1), "OVERDUE"),
        (100, 100, None, "UNPAID"),
        (100, 0, TODAY - timedelta(days=1), "PAID"),
    ],
)
def test_receivable_status_table(amount, outstanding, due, expected):
    assert ledger_service.receivable_status(
        Decimal(amount), Decimal(outstanding), due, TODAY
    ) == expected


async def _post(db, customer, branch, user, *, debit=Decimal("0"), credit=Decimal("0")):
    return await ledger_service.post(
        db, customer_id=customer.id, branch_id=branch.id, entry_type="opening_balance",
        source_type="opening_balance", source_id=uuid.uuid4(),
        business_date=business_date_today(), description="test", created_by=user.id,
        debit=debit, credit=credit,
    )


@pytest.mark.asyncio
async def test_balance_is_debits_minus_credits(db_session):
    a = await make_branch(db_session)
    b = await make_branch(db_session)
    user = await make_user(db_session, "admin")
    customer = await make_customer(db_session)
    await _post(db_session, customer, a, user, debit=Decimal("500"))
    await ledger_service.post(
        db_session, customer_id=customer.id, branch_id=a.id, entry_type="payment",
        source_type="payment", source_id=uuid.uuid4(), business_date=business_date_today(),
        description="test", created_by=user.id, credit=Decimal("200"),
    )
    assert await ledger_service.customer_balance(db_session, customer.id) == Decimal("300")
    assert await ledger_service.customer_balance(db_session, customer.id, a.id) == Decimal("300")
    assert await ledger_service.customer_balance(db_session, customer.id, b.id) == Decimal("0")


@pytest.mark.asyncio
async def test_receivables_ignore_reversed_payment_allocations(db_session):
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    customer = await make_customer(db_session, credit_limit=Decimal("1000"))
    sale = Sale(
        transaction_no=f"TXN-T-{uuid.uuid4().hex[:8]}", branch_id=branch.id,
        cashier_id=cashier.id, subtotal=Decimal("400"), total_amount=Decimal("400"),
        status="completed", customer_id=customer.id,
        due_date=business_date_today() + timedelta(days=30),
    )
    db_session.add(sale)
    await db_session.flush()
    pay = Payment(
        payment_no=f"PAY-T-{uuid.uuid4().hex[:8]}", kind="debt", customer_id=customer.id,
        branch_id=branch.id, method="cash", amount=Decimal("100"),
        business_date=business_date_today(), received_by=cashier.id, status="reversed",
    )
    db_session.add(pay)
    await db_session.flush()
    db_session.add(PaymentAllocation(payment_id=pay.id, sale_id=sale.id, amount=Decimal("100")))
    await db_session.flush()

    rows = await ledger_service.receivables(db_session, customer.id, branch.id)
    assert len(rows) == 1
    r = rows[0]
    assert r.kind == "sale" and r.id == sale.id
    assert r.reference == sale.transaction_no
    assert r.paid == Decimal("0") and r.outstanding == Decimal("400")
    assert r.status == "UNPAID"


@pytest.mark.asyncio
async def test_cashier_sees_branch_scoped_summary_but_global_available_credit(client, db_session):
    a = await make_branch(db_session)
    b = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    cashier_b = await make_user(db_session, "cashier", branch=b)
    customer = await make_customer(db_session, credit_limit=Decimal("1000000"))
    await _post(db_session, customer, a, admin, debit=Decimal("300000"))
    await _post(db_session, customer, b, admin, debit=Decimal("200000"))

    r = await client.get(f"/api/v1/customers/{customer.id}", headers=auth_headers(cashier_b))
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["balance"] == "200000.00"
    assert s["available_credit"] == "500000.00"

    r = await client.get(f"/api/v1/customers/{customer.id}", headers=auth_headers(admin))
    assert r.json()["summary"]["balance"] == "500000.00"


@pytest.mark.asyncio
async def test_credit_change_audit_records_exposure(client, db_session):
    from sqlalchemy import select
    from app.models.audit_log import AuditLog

    a = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    customer = await make_customer(db_session, credit_limit=Decimal("1000000"))
    await _post(db_session, customer, a, admin, debit=Decimal("300000"))
    r = await client.put(
        f"/api/v1/customers/{customer.id}/credit",
        json={"credit_limit": "500000", "credit_days": 30, "status": "active",
              "reason": "Punguza kikomo"},
        headers=auth_headers(admin),
    )
    assert r.status_code == 200, r.text
    row = (await db_session.execute(select(AuditLog).where(
        AuditLog.action == "CUSTOMER_CREDIT_CHANGED", AuditLog.entity_id == str(customer.id)
    ))).scalar_one()
    assert row.details["current_exposure"] == "300000.00"
