"""DB-level guarantees of the reconciliation tables (stage 3, plan Task 1):
at most one live exception per fingerprint, valid run statuses, and the
nightly demo wipe clears both tables before the rows they point at."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.business_time import business_date_today, utcnow
from app.db import seed_demo
from app.models.daily_closing import DailyClosing
from app.models.reconciliation import ReconciliationException, ReconciliationRun
from tests.conftest import make_branch, make_user
from tests.test_debt_payments import World


async def _run(db, user, **kw):
    now = utcnow()
    run = ReconciliationRun(
        run_no=kw.pop("run_no", f"UPT-TEST-{now.timestamp()}"), scope="all",
        date_from=business_date_today(), date_to=business_date_today(),
        started_at=now, finished_at=now, run_by=user.id, records_examined=0,
        discrepancy_count=0, warning_count=0, suppressed_count=0,
        status=kw.pop("status", "PASSED"), summary={}, **kw,
    )
    db.add(run)
    await db.flush()
    return run


def _exc(run, status="OPEN", fingerprint="LEDGER_BALANCE_MISMATCH:x:y", **kw):
    now = utcnow()
    return ReconciliationException(
        check_group="C", code="LEDGER_BALANCE_MISMATCH", severity="money", fingerprint=fingerprint,
        status=status, first_run_id=run.id, last_run_id=run.id, detected_at=now, last_seen_at=now, **kw,
    )


@pytest.mark.asyncio
async def test_live_fingerprint_unique(db_session):
    user = await make_user(db_session, "admin")
    run = await _run(db_session, user)
    db_session.add(_exc(run, status="DISMISSED"))
    db_session.add(_exc(run))
    await db_session.flush()  # OPEN + DISMISSED with one fingerprint is fine
    db_session.add(_exc(run))
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.flush()


@pytest.mark.asyncio
async def test_run_status_check(db_session):
    user = await make_user(db_session, "admin")
    with pytest.raises((IntegrityError, DBAPIError)):
        async with db_session.begin_nested():
            await _run(db_session, user, status="OK")


@pytest.mark.asyncio
async def test_demo_wipe_clears_reconciliation(db_session, client):
    w = await World(db_session, client).build()
    sale = await w.credit_sale(w.a, w.cashier_a, 1)
    closing = DailyClosing(branch_id=w.a.id, business_date=business_date_today(), status="closed")
    db_session.add(closing)
    await db_session.flush()
    run = await _run(db_session, w.admin)
    db_session.add(_exc(run, sale_id=sale,
                        closing_id=closing.id, customer_id=w.customer.id, branch_id=w.a.id))
    await db_session.flush()
    await seed_demo._wipe_generated_data(db_session, commit=False)
    for model in (ReconciliationException, ReconciliationRun):
        assert (await db_session.execute(select(func.count()).select_from(model))).scalar() == 0
