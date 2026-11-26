"""Read-only debt insights (brief §14, §15, §18): ageing, the debt
dashboard and factual risk indicators. Everything is derived from the
receivables stage 1 records (ledger_service.collect_receivables) and from
payments; nothing here changes what anyone owes."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.business_time import business_date_today
from app.models.customer import Customer
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.payment import Payment
from app.models.sale import Sale
from app.schemas.customer import CustomerRef, RiskOut
from app.schemas.debt import (
    AgeingOut, AgeingRow, BranchAgeing, DashboardOut, OldestDebt, TopDebtor,
)
from app.services.ledger_service import CENT, Receivable, collect_receivables

ZERO = Decimal("0.00")
BUCKETS = ("not_due", "1_30", "31_60", "61_90", "90_plus")


def ageing_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "not_due"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "90_plus"


def effective_due(r: Receivable, credit_days: int) -> date:
    """A receivable's due date; one without (shouldn't happen for stage 1
    rows, but legacy data may) gets the customer's credit term, brief §14."""
    return r.due_date or (r.date + timedelta(days=credit_days))


def _empty() -> dict[str, Decimal]:
    return {b: ZERO for b in BUCKETS}


async def _customers(db: AsyncSession, ids) -> dict[UUID, Customer]:
    if not ids:
        return {}
    rows = (await db.execute(select(Customer).where(Customer.id.in_(ids)))).scalars()
    return {c.id: c for c in rows}


def _days_overdue(r: Receivable, c: Customer, today: date) -> int:
    return (today - effective_due(r, c.credit_days)).days


async def ageing(db: AsyncSession, branch_id: UUID | None) -> AgeingOut:
    today = business_date_today()
    open_rows = await collect_receivables(db, branch_id=branch_id)
    customers = await _customers(db, {r.customer_id for r in open_rows})
    per_customer: dict[UUID, dict[str, Decimal]] = defaultdict(_empty)
    per_branch: dict[UUID, dict[str, Decimal]] = defaultdict(_empty)
    branch_names: dict[UUID, str] = {}
    totals = _empty()
    for r in open_rows:
        b = ageing_bucket(_days_overdue(r, customers[r.customer_id], today))
        per_customer[r.customer_id][b] += r.outstanding
        per_branch[r.branch_id][b] += r.outstanding
        branch_names[r.branch_id] = r.branch_name
        totals[b] += r.outstanding
    rows = [
        AgeingRow(customer=CustomerRef.model_validate(customers[cid]), buckets=bk, total=sum(bk.values(), ZERO))
        for cid, bk in per_customer.items()
    ]
    rows.sort(key=lambda x: (-x.total, x.customer.name))
    by_branch = sorted(
        (BranchAgeing(branch_id=bid, branch_name=branch_names[bid], buckets=bk, total=sum(bk.values(), ZERO))
         for bid, bk in per_branch.items()),
        key=lambda x: x.branch_name,
    )
    return AgeingOut(rows=rows, totals=totals, total=sum(totals.values(), ZERO), by_branch=by_branch)


async def all_branch_balances(db: AsyncSession, customer_ids) -> dict[UUID, Decimal]:
    """Every customer's balance across all branches (the credit limit is one
    total, decision D4), in one query."""
    if not customer_ids:
        return {}
    rows = (await db.execute(
        select(CustomerLedgerEntry.customer_id,
               func.sum(CustomerLedgerEntry.debit - CustomerLedgerEntry.credit))
        .where(CustomerLedgerEntry.customer_id.in_(customer_ids))
        .group_by(CustomerLedgerEntry.customer_id)
    )).all()
    return {cid: Decimal(v or 0).quantize(CENT) for cid, v in rows}


async def collected(db: AsyncSession, branch_id: UUID | None, date_from: date, date_to: date) -> Decimal:
    """Debt money actually recovered in a period (active debt payments)."""
    q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.kind == "debt", Payment.status == "active",
        Payment.business_date >= date_from, Payment.business_date <= date_to,
    )
    if branch_id is not None:
        q = q.where(Payment.branch_id == branch_id)
    return Decimal((await db.execute(q)).scalar() or 0).quantize(CENT)


async def dashboard(db: AsyncSession, branch_id: UUID | None, date_from: date, date_to: date) -> DashboardOut:
    today = business_date_today()
    open_rows = await collect_receivables(db, branch_id=branch_id)
    ids = {r.customer_id for r in open_rows}
    customers = await _customers(db, ids)
    balances = await all_branch_balances(db, ids)

    owed: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    overdue: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    buckets = _empty()
    oldest: tuple | None = None
    for r in open_rows:
        c = customers[r.customer_id]
        days = _days_overdue(r, c, today)
        owed[r.customer_id] += r.outstanding
        if days > 0:
            overdue[r.customer_id] += r.outstanding
        buckets[ageing_bucket(days)] += r.outstanding
        key = (effective_due(r, c.credit_days), r.date, r.reference)
        if oldest is None or key < oldest[0]:
            oldest = (key, r, days)

    over_limit = sum(1 for cid in ids if customers[cid].credit_limit > 0
                     and balances.get(cid, ZERO) > customers[cid].credit_limit)
    top = sorted(owed, key=lambda cid: (-owed[cid], customers[cid].name))[:5]
    oldest_debt = None
    if oldest:
        _, r, days = oldest
        oldest_debt = OldestDebt(
            customer=CustomerRef.model_validate(customers[r.customer_id]), reference=r.reference,
            date=r.date, days_overdue=max(0, days), outstanding=r.outstanding,
        )
    return DashboardOut(
        total_outstanding=sum(owed.values(), ZERO),
        customers_owing=len(ids),
        overdue_total=sum(overdue.values(), ZERO),
        collected_in_period=await collected(db, branch_id, date_from, date_to),
        customers_over_limit=over_limit,
        oldest_debt=oldest_debt,
        ageing=buckets,
        top_debtors=[TopDebtor(customer=CustomerRef.model_validate(customers[cid]),
                               outstanding=owed[cid], overdue=overdue[cid]) for cid in top],
    )


NEAR_LIMIT_SHARE = Decimal("0.80")
LONG_OUTSTANDING_DAYS = 90


def risk_flags(customer: Customer, scope_rows: list[Receivable], scope_balance: Decimal,
               total_balance: Decimal) -> list[str]:
    """Factual flags only (brief §15). Limit flags use the all-branch balance
    (one limit, D4); the rest use what the viewer may see (`scope_rows` are
    the open receivables in their branch scope)."""
    today = business_date_today()
    flags: list[str] = []
    limit = customer.credit_limit
    if limit > 0 and total_balance > limit:
        flags.append("OVER_LIMIT")
    elif limit > 0 and total_balance >= limit * NEAR_LIMIT_SHARE:
        flags.append("NEAR_LIMIT")
    days = [(today - effective_due(r, customer.credit_days)).days for r in scope_rows if r.outstanding > 0]
    if any(d > 0 for d in days):
        flags.append("OVERDUE")
    if any(d > LONG_OUTSTANDING_DAYS for d in days):
        flags.append("LONG_OUTSTANDING")
    if customer.status != "active" and scope_balance > 0:
        flags.append("INACTIVE_WITH_DEBT")
    return flags


async def risk_details(db: AsyncSession, customer: Customer, branch_id: UUID | None,
                       show_limit_use: bool = True) -> RiskOut:
    today = business_date_today()
    open_rows = await collect_receivables(db, customer_id=customer.id, branch_id=branch_id)
    total_balance = (await all_branch_balances(db, [customer.id])).get(customer.id, ZERO)
    purchases = select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
        Sale.customer_id == customer.id, Sale.status == "completed")
    paid = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.customer_id == customer.id, Payment.status == "active")
    if branch_id is not None:
        purchases = purchases.where(Sale.branch_id == branch_id)
        paid = paid.where(Payment.branch_id == branch_id)
    pct = None
    if show_limit_use and customer.credit_limit > 0:
        pct = (max(total_balance, ZERO) * 100 / customer.credit_limit).quantize(CENT)
    return RiskOut(
        limit_used_pct=pct,
        overdue_count=sum(1 for r in open_rows if (today - effective_due(r, customer.credit_days)).days > 0),
        oldest_open_date=min((r.date for r in open_rows), default=None),
        total_purchases=Decimal((await db.execute(purchases)).scalar() or 0).quantize(CENT),
        total_payments=Decimal((await db.execute(paid)).scalar() or 0).quantize(CENT),
    )
