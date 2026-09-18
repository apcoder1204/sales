from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.models.daily_closing import DailyClosing
from app.models.daily_closing_expense import DailyClosingExpense
from app.repositories.base import BaseRepository


class DailyClosingRepository(BaseRepository[DailyClosing]):
    model = DailyClosing

    async def create_expense(self, db: AsyncSession, data: dict) -> DailyClosingExpense:
        expense = DailyClosingExpense(**data)
        db.add(expense)
        await db.flush()
        return expense

    async def delete_expenses(self, db: AsyncSession, closing_id: UUID) -> None:
        await db.execute(delete(DailyClosingExpense).where(DailyClosingExpense.closing_id == closing_id))

    async def get_by_branch_date(
        self, db: AsyncSession, branch_id: UUID, business_date: date
    ) -> DailyClosing | None:
        """The most recent register/period for a branch on a business_date
        — a branch may have several (register_number 1, 2, ...) if it was
        closed and then reopened for a fresh operating period on the same
        date, so "the closing for today" always means the latest one."""
        result = await db.execute(
            select(DailyClosing)
            .where(
                DailyClosing.branch_id == branch_id,
                DailyClosing.business_date == business_date,
            )
            .order_by(DailyClosing.register_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_open_register(self, db: AsyncSession, branch_id: UUID) -> DailyClosing | None:
        """The single currently-open register for a branch, if any — a
        branch can have at most one (enforced by
        uq_daily_closing_one_open_per_branch)."""
        result = await db.execute(
            select(DailyClosing).where(
                DailyClosing.branch_id == branch_id, DailyClosing.status == "open"
            )
        )
        return result.scalar_one_or_none()

    async def get_max_register_number(
        self, db: AsyncSession, branch_id: UUID, business_date: date
    ) -> int:
        result = await db.execute(
            select(func.max(DailyClosing.register_number)).where(
                DailyClosing.branch_id == branch_id,
                DailyClosing.business_date == business_date,
            )
        )
        return result.scalar_one() or 0

    async def list_closings(
        self, db: AsyncSession,
        branch_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        skip: int = 0, limit: int = 20
    ) -> tuple[list[DailyClosing], int]:
        q = select(DailyClosing)
        if branch_id:
            q = q.where(DailyClosing.branch_id == branch_id)
        if from_date:
            q = q.where(DailyClosing.business_date >= from_date)
        if to_date:
            q = q.where(DailyClosing.business_date <= to_date)
        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await db.execute(
            q.order_by(DailyClosing.business_date.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count


daily_closing_repo = DailyClosingRepository()
