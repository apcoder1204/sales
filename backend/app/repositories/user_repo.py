from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_history_counts(self, db: AsyncSession, user_id: UUID) -> dict[str, int]:
        """Every FK reference to users.id that the DB won't auto-clear on
        delete (NO ACTION, per the schema — as opposed to audit_logs.user_id
        and products.created_by, which are SET NULL and don't represent
        business history that would be lost). A hard delete must be blocked
        if any of these are non-zero."""
        from app.models.sale import Sale
        from app.models.stock_request import StockRequest
        from app.models.stock_transfer import StockTransfer
        from app.models.daily_closing import DailyClosing
        from app.models.inventory_transaction import InventoryTransaction

        async def count(stmt) -> int:
            return (await db.execute(stmt)).scalar_one()

        return {
            "sales_made": await count(
                select(func.count()).select_from(Sale).where(Sale.cashier_id == user_id)
            ),
            "sales_voided": await count(
                select(func.count()).select_from(Sale).where(Sale.voided_by == user_id)
            ),
            "stock_requests_made": await count(
                select(func.count()).select_from(StockRequest).where(StockRequest.requested_by == user_id)
            ),
            "stock_requests_reviewed": await count(
                select(func.count()).select_from(StockRequest).where(StockRequest.reviewed_by == user_id)
            ),
            "transfers_executed": await count(
                select(func.count()).select_from(StockTransfer).where(StockTransfer.transferred_by == user_id)
            ),
            "closings_closed": await count(
                select(func.count()).select_from(DailyClosing).where(DailyClosing.closed_by == user_id)
            ),
            "closings_opened": await count(
                select(func.count()).select_from(DailyClosing).where(DailyClosing.opened_by == user_id)
            ),
            "closings_reopened": await count(
                select(func.count()).select_from(DailyClosing).where(DailyClosing.reopened_by == user_id)
            ),
            "inventory_transactions": await count(
                select(func.count()).select_from(InventoryTransaction).where(
                    InventoryTransaction.performed_by == user_id
                )
            ),
        }

    async def hard_delete(self, db: AsyncSession, user_id: UUID) -> None:
        await db.execute(delete(User).where(User.id == user_id))

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_users(
        self, db: AsyncSession, skip: int = 0, limit: int = 20,
        exclude_roles: list[str] | None = None,
    ) -> tuple[list[User], int]:
        from sqlalchemy import func
        from app.models.role import Role

        count_query = select(func.count()).select_from(User)
        query = select(User)
        if exclude_roles:
            count_query = count_query.join(Role, User.role_id == Role.id).where(Role.name.notin_(exclude_roles))
            query = query.join(Role, User.role_id == Role.id).where(Role.name.notin_(exclude_roles))

        count = (await db.execute(count_query)).scalar_one()
        rows = (await db.execute(
            query.order_by(User.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count


user_repo = UserRepository()
