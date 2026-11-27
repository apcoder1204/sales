"""Reconciliation on separate committed connections: two runs over the same
discrepancy leave one live exception, and two status changes on one
exception have exactly one winner."""
import asyncio

from sqlalchemy import func, select, update

from app.core.exceptions import DebtException
from app.models.audit_log import AuditLog
from app.models.daily_closing import DailyClosing
from app.models.reconciliation import ReconciliationException
from app.models.user import User
from app.schemas.daily_closing import CloseDayRequest
from app.schemas.reconciliation import RunCreate, StatusChange
from app.services import reconciliation_service
from app.services.daily_closing_service import daily_closing_service
from tests.debt_concurrency import World


async def _corrupt_world(w):
    s = w.session()
    branch = await w.branch(s)
    admin = await w.user(s, "admin")
    await s.commit()
    await s.close()
    s = w.session()  # a fresh session loads the user with its role
    closing = await daily_closing_service.close_day(s, CloseDayRequest(branch_id=branch.id), await s.get(User, admin.id))
    await s.execute(update(DailyClosing).where(DailyClosing.id == closing.id).values(total_cash=1000))
    await s.commit()
    await s.close()
    return branch, admin


async def _run(w, branch, admin):
    s = w.session()
    try:
        r = await reconciliation_service.run(s, RunCreate(scope="branch", branch_id=branch.id),
                                             await s.get(User, admin.id))
        return r.status
    finally:
        await s.close()


async def test_true_concurrent_runs_one_live_exception(monkeypatch):
    w = World()
    real_find_all = reconciliation_service.rc.find_all

    async def slow_find_all(db, scope):  # widen the window between checking and writing
        result = await real_find_all(db, scope)
        await asyncio.sleep(0.4)
        return result

    monkeypatch.setattr(reconciliation_service.rc, "find_all", slow_find_all)
    try:
        branch, admin = await _corrupt_world(w)
        assert await asyncio.gather(_run(w, branch, admin), _run(w, branch, admin), return_exceptions=True) == ["FAILED", "FAILED"]
        s = w.session()
        n = (await s.execute(select(func.count()).select_from(ReconciliationException).where(
            ReconciliationException.branch_id == branch.id,
            ReconciliationException.status.in_(("OPEN", "UNDER_REVIEW"))))).scalar()
        await s.close()
        assert n == 1
    finally:
        await w.cleanup()


async def test_true_concurrent_status_changes():
    w = World()
    try:
        branch, admin = await _corrupt_world(w)
        await _run(w, branch, admin)
        s = w.session()
        exc_id = (await s.execute(select(ReconciliationException.id).where(
            ReconciliationException.branch_id == branch.id))).scalar_one()
        await s.close()

        async def dismiss():
            session = w.session()
            try:
                await reconciliation_service.change_status(
                    session, exc_id, StatusChange(status="DISMISSED", reason="Imekubaliwa", reference="R-9"),
                    await session.get(User, admin.id))
                return "ok"
            except DebtException as e:
                return e.code
            finally:
                await session.close()

        assert sorted(map(str, await asyncio.gather(dismiss(), dismiss(), return_exceptions=True))) == ["EXCEPTION_CLOSED", "ok"]
        s = w.session()
        audits = (await s.execute(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "RECON_EXCEPTION_STATUS", AuditLog.entity_id == str(exc_id)))).scalar()
        await s.close()
        assert audits == 1
    finally:
        await w.cleanup()
