"""Reconciliation runs and exception management (spec §8, brief §20–21).

A run executes the checks for its scope (reconciliation_checks.find_all),
then writes one reconciliation_runs row and upserts reconciliation_exceptions
by fingerprint. It writes nothing else: a discrepancy is fixed with a normal
correcting action (reversal, void, old debt), never by the run.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.business_time import business_date_today, utcnow
from app.core.exceptions import NotFoundException, debt_error
from app.models.branch import Branch
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.reconciliation import LIVE_STATUSES, ReconciliationException, ReconciliationRun
from app.models.sale import Sale
from app.schemas.customer import CustomerRef
from app.schemas.reconciliation import (
    ClosingRef, ExceptionOut, RunCreate, RunDetailOut, RunOut, StatusChange,
)
from app.services import reconciliation_checks as rc
from app.services.audit_service import audit_service
from app.services.ledger_service import OPENING_BALANCE_PREFIX

LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtext('dukani_reconciliation'))")
SCOPE_ID = {"branch": ("branch_id", Branch), "customer": ("customer_id", Customer),
            "sale": ("sale_id", Sale), "payment": ("payment_id", Payment)}


def _json(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    return v


async def resolve_scope(db: AsyncSession, data: RunCreate) -> rc.Scope:
    from app.services.report_service import _resolve_period_dates  # avoids an import cycle

    date_from, date_to = _resolve_period_dates(data.period, data.from_date, data.to_date)
    if date_from > date_to:
        raise debt_error("DATE_RANGE_INVALID")
    ids = {}
    if data.scope in SCOPE_ID:
        field, model = SCOPE_ID[data.scope]
        value = getattr(data, field)
        if value is None or await db.get(model, value) is None:
            raise debt_error("RECON_SCOPE_INVALID")
        ids[field] = value
    return rc.Scope(kind=data.scope, date_from=date_from, date_to=date_to, **ids)


def scope_of(run: ReconciliationRun) -> rc.Scope:
    return rc.Scope(kind=run.scope, date_from=run.date_from, date_to=run.date_to, branch_id=run.branch_id,
                    customer_id=run.customer_id, sale_id=run.sale_id, payment_id=run.payment_id)


async def _next_run_no(db: AsyncSession) -> str:
    seq = (await db.execute(text("SELECT nextval('seq_reconciliation_number')"))).scalar()
    return f"UPT-{business_date_today().strftime('%Y%m%d')}-{seq:04d}"


async def run(db: AsyncSession, data: RunCreate, user) -> ReconciliationRun:
    scope = await resolve_scope(db, data)
    await db.execute(LOCK_SQL)  # one run at a time: fingerprints upsert cleanly
    started = utcnow()
    result = await rc.find_all(db, scope)

    fps = [f.fingerprint for f in result.findings]
    existing = (await db.execute(select(ReconciliationException).where(
        ReconciliationException.fingerprint.in_(fps),
        ReconciliationException.status.in_((*LIVE_STATUSES, "DISMISSED")),
    ))).scalars().all() if fps else []
    live = {e.fingerprint: e for e in existing if e.status in LIVE_STATUSES}
    dismissed = {}
    for e in existing:
        if e.status == "DISMISSED":
            dismissed.setdefault(e.fingerprint, set()).add(e.difference)

    kept, suppressed = [], 0
    for f in result.findings:
        if f.fingerprint not in live and f.difference in dismissed.get(f.fingerprint, ()):
            suppressed += 1
        else:
            kept.append(f)
    by_code = {}
    for f in kept:
        by_code[f.code] = by_code.get(f.code, 0) + 1
    warnings = sum(1 for f in kept if f.severity == "warning")
    status = "FAILED" if len(kept) > warnings else ("WARNING" if warnings else "PASSED")

    names = dict((await db.execute(select(Branch.id, Branch.name).where(
        Branch.id.in_(list(result.summary["branches"]))))).all()) if result.summary["branches"] else {}
    branches = sorted(
        ({"branch_id": str(b), "branch_name": names.get(b), **_json(fig)}
         for b, fig in result.summary["branches"].items()),
        key=lambda x: x["branch_name"] or "",
    )
    finished = utcnow()
    run_row = ReconciliationRun(
        run_no=await _next_run_no(db), scope=scope.kind, branch_id=scope.branch_id,
        customer_id=scope.customer_id, sale_id=scope.sale_id, payment_id=scope.payment_id,
        date_from=scope.date_from, date_to=scope.date_to, started_at=started, finished_at=finished,
        run_by=user.id, records_examined=result.examined, discrepancy_count=len(kept),
        warning_count=warnings, suppressed_count=suppressed, status=status,
        summary={"branches": branches, "by_code": by_code},
    )
    db.add(run_row)
    await db.flush()

    for f in kept:
        figures = dict(expected=f.expected, actual=f.actual, difference=f.difference, detail=f.detail)
        e = live.get(f.fingerprint)
        if e is not None:
            for k, v in figures.items():
                setattr(e, k, v)
            e.last_run_id, e.last_seen_at = run_row.id, finished
            continue
        db.add(ReconciliationException(
            check_group=f.group, code=f.code, severity=f.severity, fingerprint=f.fingerprint, status="OPEN",
            first_run_id=run_row.id, last_run_id=run_row.id, customer_id=f.customer_id, sale_id=f.sale_id,
            payment_id=f.payment_id, opening_balance_id=f.opening_balance_id, closing_id=f.closing_id,
            branch_id=f.branch_id, detected_at=finished, last_seen_at=finished, **figures,
        ))
    await db.commit()
    await audit_service.log(
        db, action="RECON_RUN", category="sales", user_id=user.id, username=user.username,
        user_role=user.role.name, branch_id=scope.branch_id, entity_type="reconciliation_run",
        entity_id=str(run_row.id), details={
            "run_no": run_row.run_no, "scope": scope.kind, "status": status, "examined": result.examined,
            "discrepancies": len(kept), "warnings": warnings, "suppressed": suppressed,
        },
    )
    return await get_run_row(db, run_row.id)


async def get_run_row(db: AsyncSession, run_id: UUID) -> ReconciliationRun:
    row = (await db.execute(select(ReconciliationRun).where(ReconciliationRun.id == run_id)
                            .execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Upatanisho", "reconciliation_run")
    return row


async def list_runs(db: AsyncSession, limit: int = 50) -> list[ReconciliationRun]:
    return (await db.execute(select(ReconciliationRun).order_by(
        ReconciliationRun.created_at.desc(), ReconciliationRun.run_no.desc()).limit(limit))).scalars().all()


def run_out(r: ReconciliationRun) -> RunOut:
    return RunOut(
        id=r.id, run_no=r.run_no, scope=r.scope, branch_id=r.branch_id,
        branch_name=r.branch.name if r.branch else None,
        customer=CustomerRef.model_validate(r.customer) if r.customer else None,
        sale_no=r.sale.transaction_no if r.sale else None,
        payment_no=r.payment.payment_no if r.payment else None,
        date_from=r.date_from, date_to=r.date_to, started_at=r.started_at, finished_at=r.finished_at,
        duration_ms=int((r.finished_at - r.started_at).total_seconds() * 1000),
        run_by_name=r.runner.full_name, records_examined=r.records_examined,
        discrepancy_count=r.discrepancy_count, warning_count=r.warning_count,
        suppressed_count=r.suppressed_count, status=r.status,
        by_code=(r.summary or {}).get("by_code", {}), summary=r.summary or {},
    )


def exception_out(e: ReconciliationException) -> ExceptionOut:
    return ExceptionOut(
        id=e.id, group=e.check_group, code=e.code, severity=e.severity, status=e.status,
        customer=CustomerRef.model_validate(e.customer) if e.customer else None,
        sale_id=e.sale_id, sale_no=e.sale.transaction_no if e.sale else None,
        payment_id=e.payment_id, payment_no=e.payment.payment_no if e.payment else None,
        opening_balance_ref=OPENING_BALANCE_PREFIX + e.opening_balance.reference if e.opening_balance else None,
        closing=ClosingRef(business_date=e.closing.business_date, register_number=e.closing.register_number)
        if e.closing else None,
        branch_id=e.branch_id, branch_name=e.branch.name if e.branch else None,
        expected=e.expected, actual=e.actual, difference=e.difference, detail=e.detail,
        detected_at=e.detected_at, last_seen_at=e.last_seen_at,
        first_run_no=e.first_run.run_no, last_run_no=e.last_run.run_no,
        status_reason=e.status_reason, status_reference=e.status_reference,
        status_by_name=e.changer.full_name if e.changer else None, status_at=e.status_at,
    )


async def run_detail(db: AsyncSession, run_id: UUID) -> RunDetailOut:
    r = await get_run_row(db, run_id)
    rows = (await db.execute(select(ReconciliationException).where(
        ReconciliationException.last_run_id == r.id).order_by(
        ReconciliationException.severity, ReconciliationException.code, ReconciliationException.detected_at)
        .execution_options(populate_existing=True))).scalars().all()
    return RunDetailOut(**run_out(r).model_dump(), exceptions=[exception_out(e) for e in rows])


TRANSITIONS = {
    "OPEN": {"UNDER_REVIEW", "RESOLVED", "DISMISSED"},
    "UNDER_REVIEW": {"OPEN", "RESOLVED", "DISMISSED"},
}


async def list_exceptions(
    db: AsyncSession, status: list[str] | None = None, code: str | None = None,
    branch_id: UUID | None = None, run_id: UUID | None = None,
) -> list[ReconciliationException]:
    """Newest first. status None → the live ones (OPEN, UNDER_REVIEW);
    an empty list → every status."""
    q = select(ReconciliationException)
    wanted = list(LIVE_STATUSES) if status is None else status
    if wanted:
        q = q.where(ReconciliationException.status.in_(wanted))
    if code:
        q = q.where(ReconciliationException.code == code)
    if branch_id:
        q = q.where(ReconciliationException.branch_id == branch_id)
    if run_id:
        q = q.where(ReconciliationException.last_run_id == run_id)
    q = q.order_by(ReconciliationException.detected_at.desc(), ReconciliationException.code)
    return (await db.execute(q.execution_options(populate_existing=True))).scalars().all()


async def change_status(db: AsyncSession, exception_id: UUID, data: StatusChange, user) -> ReconciliationException:
    """Move an exception through OPEN → UNDER_REVIEW → RESOLVED/DISMISSED
    (brief §21). Writes only the exception and an audit row: the fix itself
    is a normal correcting action, so RESOLVED is refused while a fresh
    check over the exception's last run scope still finds it."""
    e = (await db.execute(select(ReconciliationException).where(ReconciliationException.id == exception_id)
                          .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if e is None:
        raise NotFoundException("Tofauti ya upatanisho", "reconciliation_exception")
    if e.status not in TRANSITIONS:
        raise debt_error("EXCEPTION_CLOSED")
    if data.status not in TRANSITIONS[e.status]:
        raise debt_error("EXCEPTION_TRANSITION_INVALID")
    if data.status in ("RESOLVED", "DISMISSED") and not data.reference:
        raise debt_error("EXCEPTION_REFERENCE_REQUIRED")
    if data.status == "RESOLVED":
        last_run = await get_run_row(db, e.last_run_id)
        still = await rc.find_all(db, scope_of(last_run))
        if any(f.fingerprint == e.fingerprint for f in still.findings):
            raise debt_error("EXCEPTION_STILL_PRESENT")
    old = e.status
    e.status, e.status_reason, e.status_reference = data.status, data.reason, data.reference
    e.status_by, e.status_at = user.id, utcnow()
    await db.commit()
    await audit_service.log(
        db, action="RECON_EXCEPTION_STATUS", category="sales", user_id=user.id, username=user.username,
        user_role=user.role.name, branch_id=e.branch_id, entity_type="reconciliation_exception",
        entity_id=str(e.id), details={"code": e.code, "from": old, "to": data.status,
                                      "reason": data.reason, "reference": data.reference},
    )
    return (await db.execute(select(ReconciliationException).where(ReconciliationException.id == e.id)
                             .execution_options(populate_existing=True))).scalar_one()
