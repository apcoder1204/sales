"""Debt reports (brief §29 items 1–7, 9). Read-only, built on the same
receivables and payments the debt pages use, so every total here agrees
with Madeni Yote, the dashboard and the ledger."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.business_time import business_date_today
from app.models.branch import Branch
from app.models.customer import Customer
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment
from app.models.user import User
from app.schemas.customer import CustomerRef
from app.schemas.debt import (
    BranchesReport, BranchRow, BranchSummary, CollectionRow, CollectionsReport, CollectionSummary,
    CountTotal, OpeningBalanceRow, OpeningBalancesReport, OutstandingReport, OutstandingRow,
    OutstandingSummary, OverdueReport, OverdueRow, StatusCount, UtilizationReport, UtilizationRow,
    UtilizationSummary,
)
from app.services.debt_insights_service import (
    _customers, all_branch_balances, effective_due, risk_flags,
)
from app.services.ledger_service import CENT, collect_receivables

ZERO = Decimal("0.00")
METHODS = ("cash", "mobile_money", "bank_transfer")
OB_STATUSES = ("pending", "approved", "rejected", "cancelled")


def _ref(c: Customer) -> CustomerRef:
    return CustomerRef.model_validate(c)


async def _open(db: AsyncSession, branch_id: UUID | None):
    """Open receivables in scope, their customers and each row's days overdue."""
    today = business_date_today()
    rows = await collect_receivables(db, branch_id=branch_id)
    customers = await _customers(db, {r.customer_id for r in rows})
    days = {(r.kind, r.id): (today - effective_due(r, customers[r.customer_id].credit_days)).days for r in rows}
    return rows, customers, days


async def outstanding(db: AsyncSession, branch_id: UUID | None) -> OutstandingReport:
    rows, customers, days = await _open(db, branch_id)
    per: dict[UUID, list] = defaultdict(list)
    for r in rows:
        per[r.customer_id].append(r)
    totals = await all_branch_balances(db, per.keys())
    last_q = select(Payment.customer_id, func.max(Payment.created_at)).where(
        Payment.customer_id.in_(per.keys()), Payment.kind == "debt", Payment.status == "active")
    if branch_id is not None:
        last_q = last_q.where(Payment.branch_id == branch_id)
    last = dict((await db.execute(last_q.group_by(Payment.customer_id))).all()) if per else {}
    out = []
    for cid, items in per.items():
        c = customers[cid]
        balance = sum((r.outstanding for r in items), ZERO)
        out.append(OutstandingRow(
            customer=_ref(c), balance=balance,
            overdue=sum((r.outstanding for r in items if days[(r.kind, r.id)] > 0), ZERO),
            credit_limit=c.credit_limit, last_payment_at=last.get(cid),
            flags=risk_flags(c, items, balance, totals.get(cid, ZERO)),
        ))
    out.sort(key=lambda x: (-x.balance, x.customer.name))
    return OutstandingReport(rows=out, summary=OutstandingSummary(
        total_balance=sum((x.balance for x in out), ZERO),
        total_overdue=sum((x.overdue for x in out), ZERO), customers=len(out)))


async def overdue(db: AsyncSession, branch_id: UUID | None) -> OverdueReport:
    rows, customers, days = await _open(db, branch_id)
    out = [
        OverdueRow(customer=_ref(customers[r.customer_id]), branch_name=r.branch_name, reference=r.reference,
                   due_date=effective_due(r, customers[r.customer_id].credit_days),
                   days_overdue=days[(r.kind, r.id)], outstanding=r.outstanding)
        for r in rows if days[(r.kind, r.id)] > 0
    ]
    out.sort(key=lambda x: (-x.days_overdue, x.customer.name))
    return OverdueReport(rows=out, summary=CountTotal(total=sum((x.outstanding for x in out), ZERO), count=len(out)))


async def collections(db: AsyncSession, branch_id: UUID | None, date_from: date, date_to: date) -> CollectionsReport:
    q = (
        select(Payment, Customer, Branch.name, User.full_name)
        .join(Customer, Customer.id == Payment.customer_id)
        .join(Branch, Branch.id == Payment.branch_id)
        .join(User, User.id == Payment.received_by)
        .where(Payment.kind == "debt", Payment.status == "active",
               Payment.business_date >= date_from, Payment.business_date <= date_to)
        .order_by(Payment.business_date, Payment.created_at)
    )
    if branch_id is not None:
        q = q.where(Payment.branch_id == branch_id)
    out = [
        CollectionRow(payment_no=p.payment_no, business_date=p.business_date, customer=_ref(c),
                      branch_name=bname, method=p.method, amount=p.amount, received_by=uname)
        for p, c, bname, uname in (await db.execute(q)).all()
    ]
    by_method = {m: ZERO for m in METHODS}
    for x in out:
        by_method[x.method] = by_method.get(x.method, ZERO) + x.amount
    return CollectionsReport(rows=out, summary=CollectionSummary(
        total=sum((x.amount for x in out), ZERO), count=len(out), by_method=by_method))


async def branches(db: AsyncSession, branch_id: UUID | None, date_from: date, date_to: date) -> BranchesReport:
    rows, _, days = await _open(db, branch_id)
    agg: dict[UUID, dict] = {}

    def slot(bid, name):
        return agg.setdefault(bid, {"name": name, "out": ZERO, "over": ZERO, "who": set(), "coll": ZERO})

    for r in rows:
        s = slot(r.branch_id, r.branch_name)
        s["out"] += r.outstanding
        s["who"].add(r.customer_id)
        if days[(r.kind, r.id)] > 0:
            s["over"] += r.outstanding
    q = (
        select(Payment.branch_id, Branch.name, func.sum(Payment.amount))
        .join(Branch, Branch.id == Payment.branch_id)
        .where(Payment.kind == "debt", Payment.status == "active",
               Payment.business_date >= date_from, Payment.business_date <= date_to)
        .group_by(Payment.branch_id, Branch.name)
    )
    if branch_id is not None:
        q = q.where(Payment.branch_id == branch_id)
    for bid, name, total in (await db.execute(q)).all():
        slot(bid, name)["coll"] = Decimal(total).quantize(CENT)
    out = [BranchRow(branch_id=bid, branch_name=s["name"], outstanding=s["out"], overdue=s["over"],
                     customers_owing=len(s["who"]), collected_in_period=s["coll"]) for bid, s in agg.items()]
    out.sort(key=lambda x: (-x.outstanding, x.branch_name))
    return BranchesReport(rows=out, summary=BranchSummary(
        outstanding=sum((x.outstanding for x in out), ZERO), overdue=sum((x.overdue for x in out), ZERO),
        customers_owing=len({cid for s in agg.values() for cid in s["who"]}),
        collected_in_period=sum((x.collected_in_period for x in out), ZERO)))


async def credit_utilization(db: AsyncSession) -> UtilizationReport:
    """All-branch figures (one limit per customer, D4), so global roles only."""
    rows = await collect_receivables(db)
    by_customer: dict[UUID, list] = defaultdict(list)
    for r in rows:
        by_customer[r.customer_id].append(r)
    limited = set((await db.execute(select(Customer.id).where(Customer.credit_limit > 0))).scalars())
    ids = limited | set(by_customer)
    customers = await _customers(db, ids)
    totals = await all_branch_balances(db, ids)
    out = []
    for cid in ids:
        c = customers[cid]
        bal = totals.get(cid, ZERO)
        out.append(UtilizationRow(
            customer=_ref(c), credit_limit=c.credit_limit, balance=bal,
            used_pct=(max(bal, ZERO) * 100 / c.credit_limit).quantize(CENT) if c.credit_limit > 0 else None,
            available=max(ZERO, c.credit_limit - bal),
            flags=risk_flags(c, by_customer.get(cid, []), bal, bal),
        ))
    out.sort(key=lambda x: (-(x.used_pct if x.used_pct is not None else Decimal(10**6)), x.customer.name))
    return UtilizationReport(rows=out, summary=UtilizationSummary(
        customers_over_limit=sum(1 for x in out if "OVER_LIMIT" in x.flags),
        customers_near_limit=sum(1 for x in out if "NEAR_LIMIT" in x.flags)))


async def opening_balances(db: AsyncSession, branch_id: UUID | None, status: str | None) -> OpeningBalancesReport:
    q = select(OpeningBalance).order_by(OpeningBalance.effective_date, OpeningBalance.created_at)
    if branch_id is not None:
        q = q.where(OpeningBalance.branch_id == branch_id)
    all_rows = list((await db.execute(q)).scalars().all())
    summary = {s: StatusCount(count=0, amount=ZERO) for s in OB_STATUSES}
    for ob in all_rows:
        summary[ob.status].count += 1
        summary[ob.status].amount += ob.amount
    shown = [ob for ob in all_rows if status is None or ob.status == status]
    return OpeningBalancesReport(rows=[
        OpeningBalanceRow(customer=_ref(ob.customer), branch_name=ob.branch.name, amount=ob.amount,
                          effective_date=ob.effective_date, reference=ob.reference, status=ob.status,
                          entered_by_name=ob.enterer.full_name,
                          decided_by_name=ob.decider.full_name if ob.decider else None)
        for ob in shown
    ], summary=summary)


async def reconciliation(db: AsyncSession, branch_id: UUID | None, status: list[str] | None) -> "ReconciliationReport":
    """Reconciliation exceptions (brief §29 item 8). Rows follow the status
    filter (default: the live ones); the status counts cover every status."""
    from app.models.reconciliation import LIVE_STATUSES, ReconciliationException as RE
    from app.schemas.debt import ReconciliationReport, ReconciliationReportSummary
    from app.services import reconciliation_service as rs

    rows = await rs.list_exceptions(db, status, None, branch_id, None)
    counts = select(RE.status, RE.severity, func.count()).group_by(RE.status, RE.severity)
    if branch_id is not None:
        counts = counts.where(RE.branch_id == branch_id)
    by_status, money_open = {s: 0 for s in ("OPEN", "UNDER_REVIEW", "RESOLVED", "DISMISSED")}, 0
    for st, severity, n in (await db.execute(counts)).all():
        by_status[st] += n
        if st in LIVE_STATUSES and severity == "money":
            money_open += n
    by_code: dict[str, int] = {}
    for e in rows:
        by_code[e.code] = by_code.get(e.code, 0) + 1
    last = await rs.list_runs(db, limit=1)
    return ReconciliationReport(
        rows=[rs.exception_out(e) for e in rows],
        summary=ReconciliationReportSummary(by_status=by_status, by_code=by_code, money_open=money_open,
                                            last_run=rs.run_out(last[0]) if last else None),
    )
