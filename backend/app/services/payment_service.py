"""Payments: numbering, debt payments, reversals and receipts (spec §6.3).

A debt payment is received at the branch that owns the debt (decision D2):
a cashier only at their own branch, an admin at the branch they name. The
customer row lock (shared with credit checkout) serializes it against other
payments and credit sales for the same customer.
"""
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.authorization import get_active_branch_or_error, require_write_branch_access
from app.core.business_time import business_date_today, utcnow
from app.core.exceptions import NotFoundException, ValidationException, debt_error
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.repositories.daily_closing_repo import daily_closing_repo
from app.schemas.customer import CustomerRef
from app.schemas.payment import (
    AllocationOut, DebtPaymentCreate, PaymentOut, PaymentReceipt, ReceiptAllocationLine,
)
from app.services import ledger_service
from app.services.audit_service import audit_service

_LOCAL_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)


async def next_payment_no(db: AsyncSession) -> str:
    seq = (await db.execute(text("SELECT nextval('seq_payment_number')"))).scalar()
    return f"PAY-{business_date_today().strftime('%Y%m%d')}-{seq:04d}"


def _fmt(amount: Decimal) -> str:
    return f"{settings.CURRENCY} {int(amount):,}"


def _whole(amount: Decimal) -> str:
    return str(int(amount))


async def ensure_day_open(db: AsyncSession, branch_id: UUID, business_date) -> None:
    closing = await daily_closing_repo.get_by_branch_date(db, branch_id, business_date)
    if closing and closing.status == "closed":
        raise ValidationException(
            "Siku hii tayari imefungwa kwa tawi hili. Wasiliana na msimamizi kufungua tena.",
            "DAY_ALREADY_CLOSED",
        )


async def _resolve_payment_branch(db: AsyncSession, data: DebtPaymentCreate, user) -> UUID:
    if user.role.name == "cashier":
        return user.branch_id
    if data.branch_id is None:
        raise ValidationException("Chagua tawi la malipo", "BRANCH_REQUIRED")
    await require_write_branch_access(db, user, data.branch_id)
    branch = await get_active_branch_or_error(db, data.branch_id, "Tawi")
    if branch.branch_type != "pos_point":
        raise ValidationException("Malipo hupokelewa kwenye Sehemu ya Mauzo pekee", "BRANCH_NOT_POS")
    return branch.id


def _plan_allocations(open_rows, data: DebtPaymentCreate) -> list[tuple]:
    """[(receivable, amount)] — the caller's allocation checked against the
    open receivables of this customer at this branch, or FIFO."""
    if data.allocations:
        by_key = {(r.kind, r.id): r for r in open_rows}
        seen, plan = set(), []
        for a in data.allocations:
            key = ("sale", a.sale_id) if a.sale_id else ("opening_balance", a.opening_balance_id)
            r = by_key.get(key)
            if r is None or key in seen or a.amount > r.outstanding:
                raise debt_error("ALLOCATION_INVALID")
            seen.add(key)
            plan.append((r, a.amount))
        if sum((amt for _, amt in plan), Decimal("0")) != data.amount:
            raise debt_error("ALLOCATION_MISMATCH")
        return plan
    remaining, plan = data.amount, []
    for r in open_rows:  # already FIFO-ordered
        if remaining <= 0:
            break
        take = min(remaining, r.outstanding)
        plan.append((r, take))
        remaining -= take
    return plan


async def record_debt_payment(
    db: AsyncSession, customer_id: UUID, data: DebtPaymentCreate, user
) -> Payment:
    branch_id = await _resolve_payment_branch(db, data, user)
    today = business_date_today()
    await ensure_day_open(db, branch_id, today)

    customer = await ledger_service.lock_customer(db, customer_id)
    open_rows = await ledger_service.receivables(db, customer.id, branch_id, open_only=True)
    owed = sum((r.outstanding for r in open_rows), Decimal("0"))
    # Explicit allocations are checked first: naming a debt that isn't open
    # here (another branch's or customer's sale) is ALLOCATION_INVALID. Valid
    # allocations that sum to the amount already imply amount <= owed.
    if not data.allocations and data.amount > owed:
        raise debt_error("PAYMENT_EXCEEDS_DEBT", {"owed": _whole(owed)})
    plan = _plan_allocations(open_rows, data)

    balance_before = await ledger_service.customer_balance(db, customer.id, branch_id)
    payment = Payment(
        payment_no=await next_payment_no(db), kind="debt", customer_id=customer.id,
        branch_id=branch_id, method=data.method, reference=data.reference, amount=data.amount,
        business_date=today, received_by=user.id, notes=data.notes, status="active",
        balance_before=balance_before, balance_after=balance_before - data.amount,
    )
    db.add(payment)
    await db.flush()
    for r, amount in plan:
        db.add(PaymentAllocation(
            payment_id=payment.id, amount=amount,
            sale_id=r.id if r.kind == "sale" else None,
            opening_balance_id=r.id if r.kind == "opening_balance" else None,
        ))
    await ledger_service.post(
        db, customer_id=customer.id, branch_id=branch_id, entry_type="payment",
        source_type="payment", source_id=payment.id, business_date=today, credit=data.amount,
        description=f"Malipo ya deni {payment.payment_no}", created_by=user.id,
    )
    await db.commit()
    await db.refresh(payment)

    await audit_service.log(
        db, action="CUSTOMER_PAYMENT_RECORDED", category="sales",
        user_id=user.id, username=user.username, user_role=user.role.name,
        branch_id=branch_id, entity_type="payment", entity_id=str(payment.id),
        details={
            "payment_no": payment.payment_no, "customer_id": str(customer.id),
            "customer_no": customer.customer_no, "amount": str(payment.amount),
            "method": payment.method,
            "allocations": [{"reference": r.reference, "amount": str(a)} for r, a in plan],
        },
    )
    return payment


async def get_payment_for_viewing(db: AsyncSession, payment_id: UUID, user) -> Payment:
    payment = await db.get(Payment, payment_id)
    if not payment or (user.role.name == "cashier" and payment.branch_id != user.branch_id):
        raise NotFoundException("Malipo", "payment")
    return payment


async def list_customer_payments(
    db: AsyncSession, customer_id: UUID, branch_id: UUID | None
) -> list[Payment]:
    q = select(Payment).where(Payment.customer_id == customer_id)
    if branch_id is not None:
        q = q.where(Payment.branch_id == branch_id)
    return list((await db.execute(q.order_by(Payment.created_at.desc(), Payment.payment_no.desc()))).scalars().all())


async def _allocations_out(db: AsyncSession, payments: list[Payment]) -> dict[UUID, list[AllocationOut]]:
    allocs = [a for p in payments for a in p.allocations]
    sale_ids = {a.sale_id for a in allocs if a.sale_id}
    ob_ids = {a.opening_balance_id for a in allocs if a.opening_balance_id}
    sale_ref = dict((await db.execute(
        select(Sale.id, Sale.transaction_no).where(Sale.id.in_(sale_ids))
    )).all()) if sale_ids else {}
    ob_ref = dict((await db.execute(
        select(OpeningBalance.id, OpeningBalance.reference).where(OpeningBalance.id.in_(ob_ids))
    )).all()) if ob_ids else {}
    out: dict[UUID, list[AllocationOut]] = {p.id: [] for p in payments}
    for p in payments:
        for a in sorted(p.allocations, key=lambda a: str(a.id)):
            if a.sale_id:
                out[p.id].append(AllocationOut(
                    receivable_kind="sale", receivable_id=a.sale_id,
                    reference=sale_ref.get(a.sale_id, ""), amount=a.amount,
                ))
            else:
                out[p.id].append(AllocationOut(
                    receivable_kind="opening_balance", receivable_id=a.opening_balance_id,
                    reference=ledger_service.OPENING_BALANCE_PREFIX + ob_ref.get(a.opening_balance_id, ""),
                    amount=a.amount,
                ))
    return out


async def payments_out(db: AsyncSession, payments: list[Payment]) -> list[PaymentOut]:
    allocs = await _allocations_out(db, payments)
    return [
        PaymentOut(
            id=p.id, payment_no=p.payment_no, kind=p.kind,
            customer=CustomerRef.model_validate(p.customer) if p.customer else None,
            branch_id=p.branch_id, branch_name=p.branch.name, method=p.method,
            reference=p.reference, amount=p.amount, business_date=p.business_date,
            received_by_name=p.receiver.full_name, notes=p.notes, status=p.status,
            reversed_by_name=p.reverser.full_name if p.reverser else None,
            reversed_at=p.reversed_at, reversal_reason=p.reversal_reason,
            allocations=allocs[p.id], created_at=p.created_at,
        )
        for p in payments
    ]


async def build_receipt(db: AsyncSession, payment: Payment) -> PaymentReceipt:
    allocs = (await _allocations_out(db, [payment]))[payment.id]
    customer = payment.customer
    return PaymentReceipt(
        business_name=settings.APP_NAME,
        payment_no=payment.payment_no,
        customer_name=customer.name if customer else "",
        customer_no=customer.customer_no if customer else "",
        date=payment.created_at.astimezone(_LOCAL_TZ).strftime("%d/%m/%Y %H:%M"),
        amount=_fmt(payment.amount),
        method=payment.method.replace("_", " ").title(),
        reference=payment.reference,
        allocations=[ReceiptAllocationLine(reference=a.reference, amount=_fmt(a.amount)) for a in allocs],
        balance_before=_fmt(payment.balance_before) if payment.balance_before is not None else None,
        balance_after=_fmt(payment.balance_after) if payment.balance_after is not None else None,
        branch_name=payment.branch.name,
        received_by=payment.receiver.full_name,
        reversed=payment.status == "reversed",
    )


async def reverse_payment(db: AsyncSession, payment_id: UUID, reason: str, user) -> Payment:
    """Undo a debt payment (admin only, spec §6.3). The original row stays,
    marked reversed; its allocations stop counting (derived), so the debts
    it paid reopen; a ledger payment_reversal debit records it. Lock order
    customer → payment, the same as void_sale, so the two can't deadlock."""
    found = await db.get(Payment, payment_id)
    if not found:
        raise NotFoundException("Malipo", "payment")
    if found.customer_id:
        await ledger_service.lock_customer(db, found.customer_id)
    payment = (await db.execute(
        select(Payment).where(Payment.id == payment_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one()
    if payment.status == "reversed":
        raise debt_error("PAYMENT_ALREADY_REVERSED")
    if payment.kind == "sale":
        raise debt_error("SALE_PAYMENT_USE_VOID")
    await ensure_day_open(db, payment.branch_id, payment.business_date)

    payment.status = "reversed"
    payment.reversed_by = user.id
    payment.reversed_at = utcnow()
    payment.reversal_reason = reason
    await db.flush()
    original = await ledger_service.find_entry(db, "payment", payment.id, "payment")
    await ledger_service.post(
        db, customer_id=payment.customer_id, branch_id=payment.branch_id,
        entry_type="payment_reversal", source_type="payment", source_id=payment.id,
        business_date=business_date_today(), debit=payment.amount,
        reverses_entry_id=original.id if original else None,
        description=f"Malipo {payment.payment_no} yamebatilishwa", created_by=user.id,
    )
    await db.commit()
    await db.refresh(payment)
    await audit_service.log(
        db, action="CUSTOMER_PAYMENT_REVERSED", category="sales",
        user_id=user.id, username=user.username, user_role=user.role.name,
        branch_id=payment.branch_id, entity_type="payment", entity_id=str(payment.id),
        details={"payment_no": payment.payment_no, "amount": str(payment.amount), "reason": reason},
    )
    return payment
