from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def list_logs(
        self, db: AsyncSession,
        category: str | None = None,
        user_id: UUID | None = None,
        action: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        skip: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        q = select(AuditLog)
        if category:
            q = q.where(AuditLog.category == category)
        if user_id:
            q = q.where(AuditLog.user_id == user_id)
        if action:
            q = q.where(AuditLog.action == action)
        if from_date:
            q = q.where(AuditLog.created_at >= datetime.combine(from_date, datetime.min.time()))
        if to_date:
            q = q.where(AuditLog.created_at <= datetime.combine(to_date, datetime.max.time()))

        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await db.execute(
            q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count


audit_repo = AuditRepository()
