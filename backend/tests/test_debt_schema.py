"""DB-level guarantees of the customer-debt schema (spec §6.2): the ledger is
append-only, ledger rows carry exactly one side, debt payments need a
customer, allocations hit exactly one receivable, phones are unique."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.customer_ledger import CustomerLedgerEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.customer import Customer
from tests.conftest import make_branch, make_customer, make_user


async def _ledger_row(db, debit=Decimal("100"), credit=Decimal("0")):
    branch = await make_branch(db)
    user = await make_user(db, "admin")
    customer = await make_customer(db)
    import uuid
    entry = CustomerLedgerEntry(
        customer_id=customer.id,
        branch_id=branch.id,
        entry_type="opening_balance",
        source_type="opening_balance",
        source_id=uuid.uuid4(),
        debit=debit,
        credit=credit,
        business_date=date.today(),
        description="test",
        created_by=user.id,
    )
    db.add(entry)
    await db.flush()
    return entry


@pytest.mark.asyncio
async def test_ledger_update_rejected(db_session):
    entry = await _ledger_row(db_session)
    with pytest.raises(DBAPIError) as exc:
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE customer_ledger_entries SET debit = 200 WHERE id = :id"),
                {"id": entry.id},
            )
    assert "append-only" in str(exc.value)


@pytest.mark.asyncio
async def test_ledger_delete_rejected(db_session):
    entry = await _ledger_row(db_session)
    with pytest.raises(DBAPIError) as exc:
        async with db_session.begin_nested():
            await db_session.execute(
                text("DELETE FROM customer_ledger_entries WHERE id = :id"), {"id": entry.id}
            )
    assert "append-only" in str(exc.value)


@pytest.mark.asyncio
async def test_ledger_delete_allowed_in_maintenance(db_session):
    entry = await _ledger_row(db_session)
    await db_session.execute(text("SET LOCAL dukani.ledger_maintenance = 'on'"))
    await db_session.execute(
        text("DELETE FROM customer_ledger_entries WHERE id = :id"), {"id": entry.id}
    )
    left = await db_session.execute(
        text("SELECT count(*) FROM customer_ledger_entries WHERE id = :id"), {"id": entry.id}
    )
    assert left.scalar() == 0


@pytest.mark.asyncio
async def test_ledger_requires_exactly_one_side(db_session):
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await _ledger_row(db_session, debit=Decimal("0"), credit=Decimal("0"))
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await _ledger_row(db_session, debit=Decimal("10"), credit=Decimal("10"))


@pytest.mark.asyncio
async def test_debt_payment_requires_customer(db_session):
    branch = await make_branch(db_session)
    user = await make_user(db_session, "admin")
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(Payment(
                payment_no="PAY-TEST-0001", kind="debt", customer_id=None,
                branch_id=branch.id, method="cash", amount=Decimal("100"),
                business_date=date.today(), received_by=user.id, status="active",
            ))
            await db_session.flush()


@pytest.mark.asyncio
async def test_allocation_exactly_one_target(db_session):
    branch = await make_branch(db_session)
    user = await make_user(db_session, "admin")
    customer = await make_customer(db_session)
    payment = Payment(
        payment_no="PAY-TEST-0002", kind="debt", customer_id=customer.id,
        branch_id=branch.id, method="cash", amount=Decimal("100"),
        business_date=date.today(), received_by=user.id, status="active",
    )
    db_session.add(payment)
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(PaymentAllocation(
                payment_id=payment.id, sale_id=None, opening_balance_id=None,
                amount=Decimal("100"),
            ))
            await db_session.flush()


@pytest.mark.asyncio
async def test_customer_phone_unique(db_session):
    first = await make_customer(db_session)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(Customer(
                customer_no="CUS-DUP-1", name="Dup", phone=first.phone,
                customer_type="individual",
            ))
            await db_session.flush()
