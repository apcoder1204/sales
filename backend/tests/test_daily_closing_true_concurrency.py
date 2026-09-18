"""Genuine cross-connection concurrency test for daily closing — see
test_transfer_true_concurrency.py for why this can't use the rolled-back
savepoint fixtures. Commits real fixture rows, races two independent
connections against the (branch_id, business_date) unique constraint, then
deletes everything it created."""
import asyncio
import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.core.exceptions import DuplicateException
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.daily_closing import DailyClosing
from app.models.role import Role
from app.models.user import User
from app.schemas.daily_closing import CloseDayRequest
from app.services.daily_closing_service import daily_closing_service


async def test_concurrent_close_day_does_not_500_on_race():
    engine = create_async_engine(settings.DATABASE_URL)
    setup = AsyncSession(bind=engine, expire_on_commit=False)
    ids = {}
    try:
        suffix = uuid.uuid4().hex[:8]
        branch = Branch(name=f"conc_close_{suffix}", code=f"CC{suffix}", branch_type="pos_point")
        setup.add(branch)
        await setup.flush()
        ids["branch_id"] = branch.id

        admin_role = (await setup.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        admin = User(
            username=f"conc_close_{suffix}", full_name="Concurrency Closer",
            email=f"conc_close_{suffix}@test.local", password_hash=hash_password("Test1234"),
            role_id=admin_role.id, is_active=True,
        )
        setup.add(admin)
        await setup.flush()
        ids["user_id"] = admin.id
        await setup.commit()

        session_a = AsyncSession(bind=engine, expire_on_commit=False)
        session_b = AsyncSession(bind=engine, expire_on_commit=False)
        admin_a = await session_a.get(User, admin.id)
        admin_b = await session_b.get(User, admin.id)

        business_date = date.today()
        data = CloseDayRequest(branch_id=branch.id, business_date=business_date, counted_cash=0, expenses=[])

        async def attempt(session, user):
            try:
                await daily_closing_service.close_day(session, data, user)
                return "ok"
            except DuplicateException:
                return "conflict"
            finally:
                await session.close()

        results = await asyncio.gather(attempt(session_a, admin_a), attempt(session_b, admin_b))

        # The whole point of the fix: no raw IntegrityError/500 reaches the
        # caller — exactly one request wins, the other gets a clean conflict.
        assert sorted(results) == ["conflict", "ok"]

        verify = AsyncSession(bind=engine, expire_on_commit=False)
        rows = (
            await verify.execute(
                select(DailyClosing).where(
                    DailyClosing.branch_id == branch.id, DailyClosing.business_date == business_date
                )
            )
        ).scalars().all()
        assert len(rows) == 1, "exactly one closing row, not two"
        await verify.close()
    finally:
        cleanup = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            if "branch_id" in ids:
                closing_ids = (
                    await cleanup.execute(
                        select(DailyClosing.id).where(DailyClosing.branch_id == ids["branch_id"])
                    )
                ).scalars().all()
                if closing_ids:
                    from app.models.daily_closing_expense import DailyClosingExpense

                    await cleanup.execute(
                        delete(DailyClosingExpense).where(DailyClosingExpense.closing_id.in_(closing_ids))
                    )
                    await cleanup.execute(delete(DailyClosing).where(DailyClosing.id.in_(closing_ids)))
                await cleanup.execute(delete(AuditLog).where(AuditLog.branch_id == ids["branch_id"]))
            if "user_id" in ids:
                await cleanup.execute(delete(AuditLog).where(AuditLog.user_id == ids["user_id"]))
                await cleanup.execute(delete(User).where(User.id == ids["user_id"]))
            if "branch_id" in ids:
                await cleanup.execute(delete(Branch).where(Branch.id == ids["branch_id"]))
            await cleanup.commit()
        finally:
            await cleanup.close()
            await setup.close()
            await engine.dispose()
