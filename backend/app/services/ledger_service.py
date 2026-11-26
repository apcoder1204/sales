"""Customer ledger: balances, receivables and posting (spec §6.1-6.3).

The ledger (customer_ledger_entries) is the record of what a customer owes:
debit increases it, credit decreases it. Receivables (credit sales and
approved old debts) are what payments are allocated to; a receivable's paid
amount counts only allocations whose payment is still active, so a reversal
reopens it without touching any allocation row.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.business_time import business_date_for, business_date_today
from app.core.exceptions import NotFoundException
from app.models.branch import Branch
from app.models.customer import Customer
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.schemas.customer import CustomerSummary

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
OPENING_BALANCE_PREFIX = "DENI-ZAMANI "


@dataclass
class Receivable:
    kind: Literal["sale", "opening_balance"]
    id: UUID
    customer_id: UUID
    reference: str
    branch_id: UUID
    branch_name: str
    date: date
    due_date: date | None
    amount: Decimal
    paid: Decimal
    outstanding: Decimal
    status: str


def receivable_status(
    amount: Decimal, outstanding: Decimal, due_date: date | None, today: date
) -> str:
    if outstanding <= 0:
        return "PAID"
    if due_date is not None and due_date < today:
        return "OVERDUE"
    if outstanding == amount:
        return "UNPAID"
    return "PARTIALLY_PAID"


async def customer_balance(
    db: AsyncSession, customer_id: UUID, branch_id: UUID | None = None
) -> Decimal:
    q = select(
        func.coalesce(func.sum(CustomerLedgerEntry.debit), 0)
        - func.coalesce(func.sum(CustomerLedgerEntry.credit), 0)
    ).where(CustomerLedgerEntry.customer_id == customer_id)
    if branch_id is not None:
        q = q.where(CustomerLedgerEntry.branch_id == branch_id)
    return Decimal((await db.execute(q)).scalar() or 0).quantize(CENT)


def _active_paid(target_col):
    """Σ active-payment allocations per receivable id for one target column."""
    return (
        select(target_col.label("rid"), func.sum(PaymentAllocation.amount).label("paid"))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(Payment.status == "active", target_col.isnot(None))
        .group_by(target_col)
        .subquery()
    )


async def receivables(
    db: AsyncSession,
    customer_id: UUID,
    branch_id: UUID | None = None,
    open_only: bool = True,
) -> list[Receivable]:
    return await collect_receivables(db, customer_id=customer_id, branch_id=branch_id, open_only=open_only)


async def collect_receivables(
    db: AsyncSession,
    *,
    customer_id: UUID | None = None,
    branch_id: UUID | None = None,
    search: str | None = None,
    open_only: bool = True,
) -> list[Receivable]:
    """Credit sales and approved old debts, FIFO-sorted. One customer's (the
    customer page, payment allocation) or everyone's (Madeni Yote); `search`
    matches the customer's name, phone or number, or the debt's reference."""
    today = business_date_today()
    out: list[Receivable] = []
    like = f"%{search.strip()}%" if search and search.strip() else None

    def who(q, customer_col, ref_col):
        if like:
            q = q.join(Customer, Customer.id == customer_col).where(or_(
                Customer.name.ilike(like), Customer.phone.ilike(like),
                Customer.customer_no.ilike(like), ref_col.ilike(like),
            ))
        return q

    paid_sale = _active_paid(PaymentAllocation.sale_id)
    q = (
        select(Sale, Branch.name, func.coalesce(paid_sale.c.paid, 0))
        .join(Branch, Branch.id == Sale.branch_id)
        .outerjoin(paid_sale, paid_sale.c.rid == Sale.id)
        .where(Sale.customer_id.isnot(None), Sale.status == "completed")
    )
    if customer_id is not None:
        q = q.where(Sale.customer_id == customer_id)
    if branch_id is not None:
        q = q.where(Sale.branch_id == branch_id)
    if open_only:
        q = q.where(Sale.total_amount > func.coalesce(paid_sale.c.paid, 0))
    for sale, branch_name, paid in (await db.execute(who(q, Sale.customer_id, Sale.transaction_no))).all():
        paid = Decimal(paid).quantize(CENT)
        outstanding = sale.total_amount - paid
        out.append(Receivable(
            kind="sale", id=sale.id, customer_id=sale.customer_id, reference=sale.transaction_no,
            branch_id=sale.branch_id, branch_name=branch_name,
            date=business_date_for(sale.created_at), due_date=sale.due_date,
            amount=sale.total_amount, paid=paid, outstanding=outstanding,
            status=receivable_status(sale.total_amount, outstanding, sale.due_date, today),
        ))

    paid_ob = _active_paid(PaymentAllocation.opening_balance_id)
    q = (
        select(OpeningBalance, Branch.name, func.coalesce(paid_ob.c.paid, 0))
        .join(Branch, Branch.id == OpeningBalance.branch_id)
        .outerjoin(paid_ob, paid_ob.c.rid == OpeningBalance.id)
        .where(OpeningBalance.status == "approved")
    )
    if customer_id is not None:
        q = q.where(OpeningBalance.customer_id == customer_id)
    if branch_id is not None:
        q = q.where(OpeningBalance.branch_id == branch_id)
    if open_only:
        q = q.where(OpeningBalance.amount > func.coalesce(paid_ob.c.paid, 0))
    for ob, branch_name, paid in (await db.execute(who(q, OpeningBalance.customer_id, OpeningBalance.reference))).all():
        paid = Decimal(paid).quantize(CENT)
        outstanding = ob.amount - paid
        out.append(Receivable(
            kind="opening_balance", id=ob.id, customer_id=ob.customer_id,
            reference=OPENING_BALANCE_PREFIX + ob.reference,
            branch_id=ob.branch_id, branch_name=branch_name,
            date=ob.effective_date, due_date=ob.due_date,
            amount=ob.amount, paid=paid, outstanding=outstanding,
            status=receivable_status(ob.amount, outstanding, ob.due_date, today),
        ))

    if open_only:
        out = [r for r in out if r.outstanding > 0]
    # FIFO order: oldest due date first (no due date last), then oldest date.
    out.sort(key=lambda r: (r.due_date is None, r.due_date or date.max, r.date, r.reference))
    return out


async def lock_customer(db: AsyncSession, customer_id: UUID) -> Customer:
    """Lock the customer row: serializes every credit/payment decision for
    this customer across all branches (spec §9)."""
    c = (
        await db.execute(
            select(Customer).where(Customer.id == customer_id)
            .with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if not c:
        raise NotFoundException("Mteja", "customer")
    return c


async def post(
    db: AsyncSession, *,
    customer_id: UUID,
    branch_id: UUID,
    entry_type: str,
    source_type: str,
    source_id: UUID,
    business_date: date,
    description: str,
    created_by: UUID,
    debit: Decimal = ZERO,
    credit: Decimal = ZERO,
    due_date: date | None = None,
    reverses_entry_id: UUID | None = None,
) -> CustomerLedgerEntry:
    entry = CustomerLedgerEntry(
        customer_id=customer_id, branch_id=branch_id, entry_type=entry_type,
        source_type=source_type, source_id=source_id, debit=debit, credit=credit,
        business_date=business_date, due_date=due_date, description=description,
        reverses_entry_id=reverses_entry_id, created_by=created_by,
    )
    db.add(entry)
    await db.flush()
    return entry


async def find_entry(
    db: AsyncSession, source_type: str, source_id: UUID, entry_type: str
) -> CustomerLedgerEntry | None:
    return (
        await db.execute(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.source_type == source_type,
                CustomerLedgerEntry.source_id == source_id,
                CustomerLedgerEntry.entry_type == entry_type,
            )
        )
    ).scalar_one_or_none()


async def summary(db: AsyncSession, customer: Customer, branch_id: UUID | None) -> CustomerSummary:
    from app.services.debt_insights_service import risk_flags  # avoids an import cycle

    balance = await customer_balance(db, customer.id, branch_id)
    total = balance if branch_id is None else await customer_balance(db, customer.id)
    open_rows = await receivables(db, customer.id, branch_id)
    overdue = sum((r.outstanding for r in open_rows if r.status == "OVERDUE"), ZERO)
    q = select(func.max(Payment.created_at)).where(
        Payment.customer_id == customer.id, Payment.kind == "debt", Payment.status == "active"
    )
    if branch_id is not None:
        q = q.where(Payment.branch_id == branch_id)
    last_payment_at = (await db.execute(q)).scalar()
    return CustomerSummary(
        balance=balance, overdue=overdue,
        available_credit=max(ZERO, customer.credit_limit - total),
        last_payment_at=last_payment_at,
        flags=risk_flags(customer, open_rows, balance, total),
    )
