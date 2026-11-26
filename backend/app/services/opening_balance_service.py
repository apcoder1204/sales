"""Old debts from before the system (decision D5, spec §6.3 Opening balance).

One admin enters, a different admin approves or rejects (also enforced by a
DB CHECK). Only an approved row is owed: it gets a ledger debit and becomes
a receivable that debt payments can be allocated to. Approval does not check
the credit limit — the debt already exists.
"""
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_active_branch_or_error, require_write_branch_access
from app.core.business_time import business_date_today, utcnow
from app.core.exceptions import NotFoundException, ValidationException, debt_error
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment, PaymentAllocation
from app.schemas.customer import CustomerRef
from app.schemas.payment import OpeningBalanceCreate, OpeningBalanceOut
from app.services import ledger_service
from app.services.audit_service import audit_service


def to_out(ob: OpeningBalance) -> OpeningBalanceOut:
    return OpeningBalanceOut(
        id=ob.id, customer=CustomerRef.model_validate(ob.customer), branch_id=ob.branch_id,
        branch_name=ob.branch.name, amount=ob.amount, effective_date=ob.effective_date,
        due_date=ob.due_date, reference=ob.reference, description=ob.description,
        status=ob.status, entered_by=ob.entered_by, entered_by_name=ob.enterer.full_name,
        decided_by_name=ob.decider.full_name if ob.decider else None,
        decided_at=ob.decided_at, decision_note=ob.decision_note,
        cancelled_by_name=ob.canceller.full_name if ob.canceller else None,
        cancelled_at=ob.cancelled_at, cancel_reason=ob.cancel_reason, created_at=ob.created_at,
    )


async def _audit(db, user, action, ob: OpeningBalance, extra: dict | None = None):
    await audit_service.log(
        db, action=action, category="sales",
        user_id=user.id, username=user.username, user_role=user.role.name,
        branch_id=ob.branch_id, entity_type="opening_balance", entity_id=str(ob.id),
        details={
            "customer_id": str(ob.customer_id), "amount": str(ob.amount),
            "reference": ob.reference, "effective_date": ob.effective_date.isoformat(),
            **(extra or {}),
        },
    )


async def _entry_branch_id(db: AsyncSession, data: OpeningBalanceCreate, user) -> UUID:
    """A cashier enters only for their own branch; the admin must pick one."""
    if user.role.name == "cashier":
        if data.branch_id is not None:
            await require_write_branch_access(db, user, data.branch_id)
        return user.branch_id
    if data.branch_id is None:
        raise ValidationException("Chagua tawi la deni", "BRANCH_REQUIRED")
    return data.branch_id


async def create(db: AsyncSession, customer_id: UUID, data: OpeningBalanceCreate, user) -> OpeningBalance:
    branch_id = await _entry_branch_id(db, data, user)
    customer = await ledger_service.lock_customer(db, customer_id)
    branch = await get_active_branch_or_error(db, branch_id, "Tawi")
    if branch.branch_type != "pos_point":
        raise ValidationException("Deni la zamani ni la Sehemu ya Mauzo pekee", "BRANCH_NOT_POS")
    dup = (await db.execute(select(OpeningBalance.id).where(
        OpeningBalance.customer_id == customer.id,
        OpeningBalance.branch_id == branch.id,
        OpeningBalance.amount == data.amount,
        OpeningBalance.reference == data.reference.strip(),
        OpeningBalance.status.in_(("pending", "approved")),
    ))).first()
    if dup:
        raise debt_error("OPENING_BALANCE_DUPLICATE")
    ob = OpeningBalance(
        customer_id=customer.id, branch_id=branch.id, amount=data.amount,
        effective_date=data.effective_date,
        due_date=data.due_date or data.effective_date + timedelta(days=customer.credit_days),
        reference=data.reference.strip(), description=data.description,
        status="pending", entered_by=user.id,
    )
    db.add(ob)
    await db.commit()
    await db.refresh(ob)
    await _audit(db, user, "OPENING_BALANCE_ENTERED", ob)
    return ob


async def _lock_pending(db: AsyncSession, ob_id: UUID, user) -> OpeningBalance:
    ob = (await db.execute(
        select(OpeningBalance).where(OpeningBalance.id == ob_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if not ob:
        raise NotFoundException("Deni la zamani", "opening_balance")
    if ob.status != "pending":
        raise debt_error("OPENING_BALANCE_NOT_PENDING")
    return ob


async def approve(db: AsyncSession, ob_id: UUID, user, note: str | None) -> OpeningBalance:
    ob = await _lock_pending(db, ob_id, user)
    ob.status = "approved"
    ob.decided_by = user.id
    ob.decided_at = utcnow()
    ob.decision_note = note
    await db.flush()
    await ledger_service.post(
        db, customer_id=ob.customer_id, branch_id=ob.branch_id, entry_type="opening_balance",
        source_type="opening_balance", source_id=ob.id, business_date=ob.effective_date,
        debit=ob.amount, due_date=ob.due_date,
        description=f"Deni la zamani ({ob.reference})", created_by=user.id,
    )
    await db.commit()
    await db.refresh(ob)
    await _audit(db, user, "OPENING_BALANCE_APPROVED", ob, {"note": note})
    return ob


async def reject(db: AsyncSession, ob_id: UUID, user, note: str | None) -> OpeningBalance:
    if not note or len(note.strip()) < 3:
        raise ValidationException("Andika sababu ya kukataa", "REASON_REQUIRED")
    ob = await _lock_pending(db, ob_id, user)
    ob.status = "rejected"
    ob.decided_by = user.id
    ob.decided_at = utcnow()
    ob.decision_note = note.strip()
    await db.commit()
    await db.refresh(ob)
    await _audit(db, user, "OPENING_BALANCE_REJECTED", ob, {"note": ob.decision_note})
    return ob


async def cancel(db: AsyncSession, ob_id: UUID, user, reason: str) -> OpeningBalance:
    """Undo an approved old debt entered by mistake. Lock order customer →
    old debt, the same as debt payments, so a payment arriving at the same
    moment either lands first (and blocks this) or waits and finds nothing
    left to pay."""
    found = await db.get(OpeningBalance, ob_id)
    if not found:
        raise NotFoundException("Deni la zamani", "opening_balance")
    await ledger_service.lock_customer(db, found.customer_id)
    ob = (await db.execute(
        select(OpeningBalance).where(OpeningBalance.id == ob_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one()
    if ob.status != "approved":
        raise debt_error("OPENING_BALANCE_NOT_APPROVED")
    paid = (await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(PaymentAllocation.opening_balance_id == ob.id, Payment.status == "active")
    )).scalar()
    if paid and paid > 0:
        raise debt_error("OPENING_BALANCE_HAS_PAYMENTS")
    ob.status = "cancelled"
    ob.cancelled_by = user.id
    ob.cancelled_at = utcnow()
    ob.cancel_reason = reason.strip()
    await db.flush()
    original = await ledger_service.find_entry(db, "opening_balance", ob.id, "opening_balance")
    await ledger_service.post(
        db, customer_id=ob.customer_id, branch_id=ob.branch_id, entry_type="opening_void",
        source_type="opening_balance", source_id=ob.id, business_date=business_date_today(),
        credit=ob.amount, reverses_entry_id=original.id if original else None,
        description=f"Deni la zamani ({ob.reference}) limebatilishwa", created_by=user.id,
    )
    await db.commit()
    await db.refresh(ob)
    await _audit(db, user, "OPENING_BALANCE_CANCELLED", ob, {"reason": ob.cancel_reason})
    return ob


async def list_(db: AsyncSession, status: str | None, branch_id: UUID | None) -> list[OpeningBalance]:
    q = select(OpeningBalance)
    if status:
        q = q.where(OpeningBalance.status == status)
    if branch_id:
        q = q.where(OpeningBalance.branch_id == branch_id)
    return list((await db.execute(q.order_by(OpeningBalance.created_at.desc()))).scalars().all())
