"""Reconciliation checks (spec §8, brief §19). Every function here only
reads: it loads its scope in a few bulk queries and returns Findings. The
run (reconciliation_service) decides what to persist; nothing here writes.

Groups: A sales and receivables, B payment allocation, C customer ledger,
E sales per period, F P&L, G daily closings. Group D (branch) has no code
of its own: branch totals go in the summary, and any gap there is exactly
the sum of that branch's LEDGER_BALANCE_MISMATCH findings (plan ruling).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.business_time import business_date_for, utc_range_for_business_date, utcnow
from app.models.branch import Branch
from app.models.daily_closing import DailyClosing
from app.models.customer_ledger import CustomerLedgerEntry as L
from app.models.opening_balance import OpeningBalance as OB
from app.models.payment import Payment, PaymentAllocation as PA
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.repositories.sale_repo import credit_at_sale_expr, sale_repo
from app.services import ledger_service

ZERO = Decimal("0.00")
WARNING_CODES = frozenset({"DUPLICATE_PAYMENT_REFERENCE", "LEGACY_PAYMENT_MISMATCH"})


@dataclass(frozen=True)
class Finding:
    group: str
    code: str
    severity: Literal["money", "warning"]
    fingerprint: str
    branch_id: UUID | None = None
    customer_id: UUID | None = None
    sale_id: UUID | None = None
    payment_id: UUID | None = None
    opening_balance_id: UUID | None = None
    closing_id: UUID | None = None
    expected: Decimal | None = None
    actual: Decimal | None = None
    detail: str = ""

    @property
    def difference(self) -> Decimal | None:
        if self.expected is None or self.actual is None:
            return None
        return self.actual - self.expected


@dataclass(frozen=True)
class Scope:
    kind: Literal["all", "branch", "customer", "sale", "payment"]
    date_from: date
    date_to: date
    branch_id: UUID | None = None
    customer_id: UUID | None = None
    sale_id: UUID | None = None
    payment_id: UUID | None = None


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)
    examined: int = 0
    summary: dict = field(default_factory=dict)


def _finding(group: str, code: str, key: str, **kw) -> Finding:
    severity = "warning" if code in WARNING_CODES else "money"
    return Finding(group=group, code=code, severity=severity, fingerprint=f"{code}:{key}", **kw)


def _d(v) -> Decimal:
    return Decimal(v or 0).quantize(Decimal("0.01"))


# ── Scope filters ───────────────────────────────────────────────────────────

def _payments_of_sale(sale_id: UUID):
    return select(PA.payment_id).where(PA.sale_id == sale_id)


def _sale_conds(s: Scope) -> list:
    if s.kind == "branch":
        return [Sale.branch_id == s.branch_id]
    if s.kind == "customer":
        return [Sale.customer_id == s.customer_id]
    if s.kind == "sale":
        return [Sale.id == s.sale_id]
    if s.kind == "payment":
        return [Sale.id.in_(select(PA.sale_id).where(PA.payment_id == s.payment_id))]
    return []


def _payment_conds(s: Scope) -> list:
    if s.kind == "branch":
        return [Payment.branch_id == s.branch_id]
    if s.kind == "customer":
        return [Payment.customer_id == s.customer_id]
    if s.kind == "sale":
        return [Payment.id.in_(_payments_of_sale(s.sale_id))]
    if s.kind == "payment":
        return [Payment.id == s.payment_id]
    return []


def _ob_conds(s: Scope) -> list:
    if s.kind == "branch":
        return [OB.branch_id == s.branch_id]
    if s.kind == "customer":
        return [OB.customer_id == s.customer_id]
    if s.kind == "sale":
        return [false()]
    if s.kind == "payment":
        return [OB.id.in_(select(PA.opening_balance_id).where(PA.payment_id == s.payment_id))]
    return []


def _ledger_conds(s: Scope) -> list:
    if s.kind == "branch":
        return [L.branch_id == s.branch_id]
    if s.kind == "customer":
        return [L.customer_id == s.customer_id]
    if s.kind == "sale":
        return [or_(
            and_(L.source_type == "sale", L.source_id == s.sale_id),
            and_(L.source_type == "payment", L.source_id.in_(_payments_of_sale(s.sale_id))),
        )]
    if s.kind == "payment":
        return [L.source_type == "payment", L.source_id == s.payment_id]
    return []


async def _branch_names(db: AsyncSession, ids) -> dict:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return dict((await db.execute(select(Branch.id, Branch.name).where(Branch.id.in_(ids)))).all())


# ── A: sales and receivables ────────────────────────────────────────────────

async def check_receivables(db: AsyncSession, scope: Scope) -> CheckResult:
    res = CheckResult()
    conds = [Sale.status == "completed", *_sale_conds(scope)]
    sales = (await db.execute(select(
        Sale.id, Sale.total_amount, Sale.customer_id, Sale.branch_id, Sale.payment_method, Sale.subtotal,
    ).where(*conds))).all()
    sale_ids = select(Sale.id).where(*conds)
    items = dict((await db.execute(
        select(SaleItem.sale_id, func.sum(SaleItem.line_total))
        .where(SaleItem.sale_id.in_(sale_ids)).group_by(SaleItem.sale_id)
    )).all())
    allocs = defaultdict(list)
    for sid, amount, kind, method, status in (await db.execute(
        select(PA.sale_id, PA.amount, Payment.kind, Payment.method, Payment.status)
        .join(Payment, Payment.id == PA.payment_id).where(PA.sale_id.in_(sale_ids))
    )).all():
        allocs[sid].append((_d(amount), kind, method, status))

    for sid, total, customer_id, branch_id, legacy_method, subtotal in sales:
        total = _d(total)
        active = [a for a in allocs[sid] if a[3] == "active"]
        paid = sum((a[0] for a in active), ZERO)
        ids = dict(sale_id=sid, customer_id=customer_id, branch_id=branch_id)
        if paid > total:
            res.findings.append(_finding("A", "RECEIVABLE_OVERPAID", str(sid), expected=total, actual=paid, **ids))
        if customer_id is None and paid != total:
            res.findings.append(_finding("A", "WALKIN_SALE_UNPAID", str(sid), expected=total, actual=paid, **ids))
        # Items add up to the subtotal. Sales from before VAT was removed
        # (migration 0007) have total = subtotal + VAT; that is history, not
        # a discrepancy, so the total is never compared with the items.
        item_total = _d(items.get(sid))
        if item_total != _d(subtotal):
            res.findings.append(_finding("A", "SALE_ITEMS_MISMATCH", str(sid), expected=item_total,
                                         actual=_d(subtotal), **ids))
        if legacy_method is not None:
            till = [a for a in active if a[1] == "sale"]
            ok = len(till) == 1 and till[0][2] == legacy_method and till[0][0] == total
            if not ok:
                res.findings.append(_finding(
                    "A", "LEGACY_PAYMENT_MISMATCH", str(sid), expected=total,
                    actual=sum((a[0] for a in till), ZERO), detail=legacy_method, **ids))

    ob_conds = [OB.status == "approved", *_ob_conds(scope)]
    obs = (await db.execute(select(OB.id, OB.amount, OB.customer_id, OB.branch_id).where(*ob_conds))).all()
    ob_paid = dict((await db.execute(
        select(PA.opening_balance_id, func.sum(PA.amount)).join(Payment, Payment.id == PA.payment_id)
        .where(Payment.status == "active", PA.opening_balance_id.in_(select(OB.id).where(*ob_conds)))
        .group_by(PA.opening_balance_id)
    )).all())
    for oid, amount, customer_id, branch_id in obs:
        paid = _d(ob_paid.get(oid))
        if paid > _d(amount):
            res.findings.append(_finding(
                "A", "RECEIVABLE_OVERPAID", str(oid), expected=_d(amount), actual=paid,
                opening_balance_id=oid, customer_id=customer_id, branch_id=branch_id))
    res.examined = len(sales) + len(obs)
    return res


# ── B: payment allocation ───────────────────────────────────────────────────

async def check_allocations(db: AsyncSession, scope: Scope) -> CheckResult:
    res = CheckResult()
    conds = _payment_conds(scope)
    payments = (await db.execute(select(
        Payment.id, Payment.kind, Payment.status, Payment.customer_id, Payment.branch_id,
        Payment.amount, Payment.business_date,
    ).where(*conds))).all()
    rows = (await db.execute(
        select(
            PA.id, PA.payment_id, PA.sale_id, PA.opening_balance_id, PA.amount,
            Sale.branch_id, Sale.customer_id, Sale.status, Sale.created_at,
            OB.branch_id, OB.customer_id, OB.status,
        )
        .outerjoin(Sale, Sale.id == PA.sale_id)
        .outerjoin(OB, OB.id == PA.opening_balance_id)
        .where(PA.payment_id.in_(select(Payment.id).where(*conds)))
    )).all()
    by_payment = defaultdict(list)
    for r in rows:
        by_payment[r[1]].append(r)
    names = await _branch_names(db, [p.branch_id for p in payments] + [r[5] or r[9] for r in rows])

    for p in payments:
        amount = _d(p.amount)
        mine = by_payment[p.id]
        ids = dict(payment_id=p.id, customer_id=p.customer_id, branch_id=p.branch_id)
        allocated = sum((_d(r[4]) for r in mine), ZERO)
        if allocated != amount:
            res.findings.append(_finding("B", "ALLOCATION_TOTAL_MISMATCH", str(p.id),
                                         expected=amount, actual=allocated, **ids))
        for (aid, _pid, sale_id, ob_id, a_amount, s_branch, s_customer, s_status, _created,
             o_branch, o_customer, o_status) in mine:
            t_branch = s_branch if sale_id else o_branch
            t_customer = s_customer if sale_id else o_customer
            target = dict(sale_id=sale_id, opening_balance_id=ob_id)
            if t_branch != p.branch_id:
                res.findings.append(_finding(
                    "B", "ALLOCATION_BRANCH_MISMATCH", str(aid), payment_id=p.id, customer_id=p.customer_id,
                    branch_id=p.branch_id, detail=f"{names.get(p.branch_id, '?')} → {names.get(t_branch, '?')}",
                    **target))
            if p.customer_id is not None and t_customer != p.customer_id:
                res.findings.append(_finding("B", "ALLOCATION_CUSTOMER_MISMATCH", str(aid), **ids, **target))
            orphan = (sale_id and s_status != "completed") or (ob_id and o_status != "approved")
            if p.status == "active" and orphan:
                res.findings.append(_finding(
                    "B", "ORPHAN_ALLOCATION", str(aid), expected=ZERO, actual=_d(a_amount),
                    detail=s_status if sale_id else o_status, **ids, **target))
        if p.kind == "sale":
            reason = None
            if any(r[3] for r in mine):
                reason = "opening_balance"
            elif len(mine) > 1:
                reason = "many_sales"
            elif len(mine) == 1 and business_date_for(mine[0][8]) != p.business_date:
                reason = "other_day"
            if reason:
                res.findings.append(_finding("B", "TILL_PAYMENT_MISMATCH", str(p.id), detail=reason,
                                             sale_id=mine[0][2] if mine else None, **ids))
    res.examined = len(payments)
    return res


# ── C: customer ledger ──────────────────────────────────────────────────────

def _entry_amount(row) -> Decimal:
    return _d(row.debit) if row.debit else _d(row.credit)


async def check_ledger(db: AsyncSession, scope: Scope) -> CheckResult:
    res = CheckResult()
    cols = (L.id, L.customer_id, L.branch_id, L.entry_type, L.source_type, L.source_id, L.debit, L.credit)
    lconds = _ledger_conds(scope)
    actual = {(r.source_type, r.source_id, r.entry_type): r
              for r in (await db.execute(select(*cols).where(*lconds))).all()}

    def docs_filter(conds, id_col, stype):
        """Documents in scope, plus those the in-scope ledger rows point at.
        Subqueries, never Python id lists: a busy branch would exceed
        asyncpg's 32,767 bind parameters."""
        if not conds:
            return []  # scope 'all': every document
        refs = select(L.source_id).where(L.source_type == stype, *lconds)
        return [or_(and_(*conds), id_col.in_(refs))]

    sales = (await db.execute(select(Sale.id, Sale.customer_id, Sale.branch_id, Sale.status, Sale.total_amount)
                              .where(Sale.customer_id.isnot(None),
                                     *docs_filter(_sale_conds(scope), Sale.id, "sale")))).all()
    payments = (await db.execute(select(Payment.id, Payment.customer_id, Payment.branch_id, Payment.status,
                                        Payment.amount)
                                 .where(Payment.customer_id.isnot(None),
                                        *docs_filter(_payment_conds(scope), Payment.id, "payment")))).all()
    obs = (await db.execute(select(OB.id, OB.customer_id, OB.branch_id, OB.status, OB.amount)
                            .where(OB.status.in_(("approved", "cancelled")),
                                   *docs_filter(_ob_conds(scope), OB.id, "opening_balance")))).all()

    # Expected rows: key → (side, amount, customer, branch, finding ids)
    expected = {}
    for s in sales:
        ids = dict(sale_id=s.id)
        expected[("sale", s.id, "sale")] = ("debit", _d(s.total_amount), s.customer_id, s.branch_id, ids)
        if s.status == "voided":
            expected[("sale", s.id, "sale_void")] = ("credit", _d(s.total_amount), s.customer_id, s.branch_id, ids)
    for p in payments:
        ids = dict(payment_id=p.id)
        expected[("payment", p.id, "payment")] = ("credit", _d(p.amount), p.customer_id, p.branch_id, ids)
        if p.status == "reversed":
            expected[("payment", p.id, "payment_reversal")] = ("debit", _d(p.amount), p.customer_id, p.branch_id, ids)
    for o in obs:
        ids = dict(opening_balance_id=o.id)
        expected[("opening_balance", o.id, "opening_balance")] = ("debit", _d(o.amount), o.customer_id, o.branch_id, ids)
        if o.status == "cancelled":
            expected[("opening_balance", o.id, "opening_void")] = ("credit", _d(o.amount), o.customer_id, o.branch_id, ids)

    if scope.kind != "all":
        # Ledger rows of the in-scope documents that sit outside the scope
        # (e.g. posted to the wrong branch), so they show as mismatches.
        doc_rows = or_(
            and_(L.source_type == "sale", L.source_id.in_(
                select(Sale.id).where(Sale.customer_id.isnot(None), *docs_filter(_sale_conds(scope), Sale.id, "sale")))),
            and_(L.source_type == "payment", L.source_id.in_(
                select(Payment.id).where(Payment.customer_id.isnot(None),
                                         *docs_filter(_payment_conds(scope), Payment.id, "payment")))),
            and_(L.source_type == "opening_balance", L.source_id.in_(
                select(OB.id).where(OB.status.in_(("approved", "cancelled")),
                                    *docs_filter(_ob_conds(scope), OB.id, "opening_balance")))),
        )
        known = {r.id for r in actual.values()}
        for r in (await db.execute(select(*cols).where(doc_rows))).all():
            if r.id not in known:
                actual[(r.source_type, r.source_id, r.entry_type)] = r

    for key, (side, amount, customer_id, branch_id, ids) in expected.items():
        row = actual.get(key)
        where = dict(customer_id=customer_id, branch_id=branch_id, **ids)
        if row is None:
            res.findings.append(_finding("C", "MISSING_LEDGER_ENTRY", f"{key[1]}:{key[2]}",
                                         expected=amount, actual=ZERO, detail=key[2], **where))
            continue
        got = _d(row.debit if side == "debit" else row.credit)
        if got != amount or (row.debit and row.credit):
            res.findings.append(_finding("C", "LEDGER_ENTRY_MISMATCH", f"{row.id}:amount",
                                         expected=amount, actual=got, detail="amount", **where))
        if row.customer_id != customer_id:
            res.findings.append(_finding("C", "LEDGER_ENTRY_MISMATCH", f"{row.id}:customer", detail="customer", **where))
        if row.branch_id != branch_id:
            res.findings.append(_finding("C", "LEDGER_ENTRY_MISMATCH", f"{row.id}:branch", detail="branch", **where))
    doc_found = {"sale": {s.id for s in sales}, "payment": {p.id for p in payments},
                 "opening_balance": {o.id for o in obs}}
    id_field = {"sale": "sale_id", "payment": "payment_id", "opening_balance": "opening_balance_id"}
    for key, row in actual.items():
        if key in expected:
            continue
        extra = {id_field[key[0]]: key[1]} if key[1] in doc_found.get(key[0], ()) else {}
        res.findings.append(_finding("C", "ORPHAN_LEDGER_ENTRY", str(row.id), expected=ZERO,
                                     actual=_entry_amount(row), detail=key[2], customer_id=row.customer_id,
                                     branch_id=row.branch_id, **extra))

    # Ledger balance vs receivables, per (customer, branch).
    bal_conds, rec_args = [], {}
    if scope.kind == "branch":
        bal_conds, rec_args = [L.branch_id == scope.branch_id], {"branch_id": scope.branch_id}
    elif scope.kind == "customer":
        bal_conds, rec_args = [L.customer_id == scope.customer_id], {"customer_id": scope.customer_id}
    elif scope.kind == "sale":
        sale = (await db.execute(select(Sale.customer_id, Sale.branch_id).where(Sale.id == scope.sale_id))).first()
        if sale is None or sale.customer_id is None:
            bal_conds = None
        else:
            bal_conds = [L.customer_id == sale.customer_id, L.branch_id == sale.branch_id]
            rec_args = {"customer_id": sale.customer_id, "branch_id": sale.branch_id}
    elif scope.kind == "payment":
        bal_conds = None
    if bal_conds is not None:
        ledger = {(c, b): _d(v) for c, b, v in (await db.execute(
            select(L.customer_id, L.branch_id, func.sum(L.debit - L.credit))
            .where(*bal_conds).group_by(L.customer_id, L.branch_id)
        )).all()}
        receivables = defaultdict(lambda: ZERO)
        for r in await ledger_service.collect_receivables(db, open_only=False, **rec_args):
            receivables[(r.customer_id, r.branch_id)] += r.outstanding
        branches = defaultdict(lambda: {"ledger": ZERO, "receivables": ZERO})
        for key in set(ledger) | set(receivables):
            lv, rv = ledger.get(key, ZERO), receivables.get(key, ZERO)
            branches[key[1]]["ledger"] += lv
            branches[key[1]]["receivables"] += rv
            if lv != rv:
                res.findings.append(_finding("C", "LEDGER_BALANCE_MISMATCH", f"{key[0]}:{key[1]}",
                                             expected=rv, actual=lv, customer_id=key[0], branch_id=key[1]))
        res.summary = {"branches": dict(branches)}
    res.examined = len(actual)
    return res


# ── E: sales per period ─────────────────────────────────────────────────────

def _window(scope: Scope):
    return utc_range_for_business_date(scope.date_from)[0], utc_range_for_business_date(scope.date_to)[1]


def _branch_filter(col, scope: Scope) -> list:
    return [col == scope.branch_id] if scope.kind == "branch" else []


async def check_sales_period(db: AsyncSession, scope: Scope) -> CheckResult:
    """Per branch for the period: what was sold, taken at the till, given on
    credit, collected against debt and voided (brief §19 E). Every figure
    reuses the definitions the daily closing uses. It has no codes of its
    own: a voided sale with an active payment is B's ORPHAN_ALLOCATION."""
    res = CheckResult()
    from_dt, to_dt = _window(scope)
    sale_win = (Sale.created_at >= from_dt, Sale.created_at <= to_dt, *_branch_filter(Sale.branch_id, scope))
    pay_win = (Payment.created_at >= from_dt, Payment.created_at <= to_dt, Payment.status == "active",
               *_branch_filter(Payment.branch_id, scope))
    branches = defaultdict(lambda: {"sales_total": ZERO, "till_collected": ZERO, "credit_given": ZERO,
                                    "debt_collected": ZERO, "voided_count": 0, "voided_total": ZERO})
    for b, total, credit in (await db.execute(
        select(Sale.branch_id, func.sum(Sale.total_amount), func.sum(credit_at_sale_expr()))
        .where(Sale.status == "completed", *sale_win).group_by(Sale.branch_id)
    )).all():
        branches[b]["sales_total"], branches[b]["credit_given"] = _d(total), _d(credit)
    for b, n, total in (await db.execute(
        select(Sale.branch_id, func.count(Sale.id), func.sum(Sale.total_amount))
        .where(Sale.status == "voided", *sale_win).group_by(Sale.branch_id)
    )).all():
        branches[b]["voided_count"], branches[b]["voided_total"] = int(n), _d(total)
    for b, kind, total in (await db.execute(
        select(Payment.branch_id, Payment.kind, func.sum(Payment.amount))
        .where(*pay_win).group_by(Payment.branch_id, Payment.kind)
    )).all():
        branches[b]["till_collected" if kind == "sale" else "debt_collected"] = _d(total)
    res.summary = {"branches": dict(branches)}
    return res


# ── F: P&L ──────────────────────────────────────────────────────────────────

async def check_pnl(db: AsyncSession, scope: Scope) -> CheckResult:
    """P&L revenue (the real report) = Σ subtotal of completed sales in the
    same window, per branch. Payments are never an input (brief §19 F)."""
    from app.services.report_service import _get_date_range, report_service  # avoids an import cycle

    res = CheckResult()
    branch_id = scope.branch_id if scope.kind == "branch" else None
    report = await report_service.get_profit_loss_report(db, "custom", scope.date_from, scope.date_to, branch_id)
    if branch_id is not None:  # the report lists branches only for all-branch requests
        pnl = {branch_id: _d(Decimal(str(report.summary.revenue)))}
    else:
        pnl = {b.branch_id: _d(Decimal(str(b.revenue))) for b in report.branches}
    from_dt, to_dt = _get_date_range("custom", scope.date_from, scope.date_to)
    sold = {b: _d(v) for b, v in (await db.execute(
        select(Sale.branch_id, func.sum(Sale.subtotal))
        .where(Sale.status == "completed", Sale.created_at >= from_dt, Sale.created_at <= to_dt,
               *_branch_filter(Sale.branch_id, scope))
        .group_by(Sale.branch_id)
    )).all()}
    branches = {}
    for b in set(pnl) | set(sold):
        expected, actual = sold.get(b, ZERO), pnl.get(b, ZERO)
        branches[b] = {"pnl_revenue": actual}
        if expected != actual:
            res.findings.append(_finding(
                "F", "PNL_REVENUE_MISMATCH", f"{b}:{scope.date_from}:{scope.date_to}",
                expected=expected, actual=actual, branch_id=b, detail=f"{scope.date_from}…{scope.date_to}"))
    res.summary = {"branches": branches}
    return res


# ── G: daily closings and payment references ────────────────────────────────

CLOSING_FIELDS = (
    ("total_cash", "cash"), ("total_mobile_money", "mobile_money"), ("total_bank_transfer", "bank_transfer"),
    ("total_revenue", "revenue"), ("total_sales_count", "count"),
    ("total_credit_given", "credit_given"), ("total_debt_collected", "debt_collected"),
)


def closing_window(c: DailyClosing):
    """The window close_day computed this register's totals over: from its
    explicit opening to its closing, or (a register never explicitly
    opened) from the start of its Tanzania business day to its closing."""
    closed = c.closed_at.replace(tzinfo=None) if c.closed_at else None
    if c.opened_at:
        return c.opened_at.replace(tzinfo=None), closed or utcnow()
    # Never explicitly opened: the whole business day, but only up to when
    # it closed — a second register opened later that day has its own sales.
    day_start, day_end = utc_range_for_business_date(c.business_date)
    return day_start, min(day_end, closed) if closed else day_end


async def _duplicate_references(db: AsyncSession, scope: Scope) -> list[Finding]:
    norm = func.upper(func.trim(Payment.reference))
    conds = [Payment.status == "active", Payment.method.in_(("mobile_money", "bank_transfer")),
             Payment.reference.isnot(None), func.trim(Payment.reference) != ""]
    if scope.kind == "branch":
        conds.append(Payment.branch_id == scope.branch_id)
    elif scope.kind == "payment":
        conds.append(norm == select(norm).where(Payment.id == scope.payment_id).scalar_subquery())
    groups = defaultdict(list)
    for ref, pid, no, branch_id, created in (await db.execute(
        select(norm, Payment.id, Payment.payment_no, Payment.branch_id, Payment.created_at).where(*conds)
    )).all():
        groups[ref].append((created, pid, no, branch_id))
    out = []
    for ref, rows in groups.items():
        if len(rows) < 2:
            continue
        rows.sort()
        branch_ids = {r[3] for r in rows}
        # expected 1 use, actual n uses: a further reuse changes the
        # difference, so a dismissed finding speaks up again.
        out.append(_finding("G", "DUPLICATE_PAYMENT_REFERENCE", ref, payment_id=rows[0][1],
                            expected=Decimal(1), actual=Decimal(len(rows)),
                            branch_id=branch_ids.pop() if len(branch_ids) == 1 else None,
                            detail=f"{ref}: " + ", ".join(r[2] for r in rows)))
    return out


async def check_closings(db: AsyncSession, scope: Scope) -> CheckResult:
    res = CheckResult()
    closings = (await db.execute(select(DailyClosing).where(
        DailyClosing.status == "closed",
        DailyClosing.business_date >= scope.date_from, DailyClosing.business_date <= scope.date_to,
        *_branch_filter(DailyClosing.branch_id, scope),
    ))).scalars().all()
    for c in closings:
        from_dt, to_dt = closing_window(c)
        totals = await sale_repo.get_totals_by_payment_method(db, c.branch_id, from_dt, to_dt)
        for stored_field, key in CLOSING_FIELDS:
            stored, recomputed = getattr(c, stored_field), totals[key]
            if key == "count":
                stored, recomputed = Decimal(int(stored or 0)), Decimal(int(recomputed))
            else:
                stored, recomputed = _d(stored), _d(Decimal(str(recomputed)))
            if stored != recomputed:
                res.findings.append(_finding(
                    "G", "CLOSING_TOTAL_MISMATCH", f"{c.id}:{stored_field}", expected=recomputed,
                    actual=stored, closing_id=c.id, branch_id=c.branch_id, detail=stored_field))
    res.findings += await _duplicate_references(db, scope)
    res.examined = len(closings)
    return res


# ── All checks for a scope ──────────────────────────────────────────────────

SCOPE_CHECKS = {
    "all": (check_receivables, check_allocations, check_ledger, check_sales_period, check_pnl, check_closings),
    "branch": (check_receivables, check_allocations, check_ledger, check_sales_period, check_pnl, check_closings),
    "customer": (check_receivables, check_allocations, check_ledger),
    "sale": (check_receivables, check_allocations, check_ledger),
    "payment": (check_allocations, check_ledger),
}


async def _payment_references(db: AsyncSession, scope: Scope) -> CheckResult:
    return CheckResult(findings=await _duplicate_references(db, scope))


async def find_all(db: AsyncSession, scope: Scope) -> CheckResult:
    """Run every check that applies to the scope (plan "Scope → checks")
    and merge their findings, counts and per-branch summaries."""
    checks = list(SCOPE_CHECKS[scope.kind])
    if scope.kind == "payment":
        checks.append(_payment_references)
    out = CheckResult(summary={"branches": {}})
    seen = set()
    for check in checks:
        r = await check(db, scope)
        for f in r.findings:
            if f.fingerprint not in seen:
                seen.add(f.fingerprint)
                out.findings.append(f)
        out.examined += r.examined
        for b, figures in r.summary.get("branches", {}).items():
            out.summary["branches"].setdefault(b, {}).update(figures)
    return out
