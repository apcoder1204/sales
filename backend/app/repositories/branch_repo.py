from uuid import UUID
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.branch import Branch
from app.repositories.base import BaseRepository

# Audit actions that describe managing the branch REGISTRY RECORD itself
# (create/edit/deactivate), not real business activity conducted at that
# branch. These must never block a hard delete — a branch that was created
# and immediately deleted by mistake, with zero real business activity,
# always has at least its own BRANCH_CREATED row referencing it, which would
# otherwise make hard-delete permanently unreachable through the real API
# (branch_id has no ON DELETE SET NULL, unlike audit_log.user_id).
BRANCH_LIFECYCLE_ACTIONS = ("BRANCH_CREATED", "BRANCH_UPDATED", "BRANCH_DEACTIVATED")


class BranchRepository(BaseRepository[Branch]):
    model = Branch

    async def list_all(self, db: AsyncSession) -> list[Branch]:
        """The full, unfiltered global registry — only ever reached through
        the admin-only branch-management endpoints. Every other branch list
        in the app (get_authorized_branches, branch_context) is scoped by
        role; this one deliberately is not, by design — see app/api/v1/branches.py."""
        result = await db.execute(select(Branch).order_by(Branch.name))
        return list(result.scalars().all())

    async def get_by_name_or_code(self, db: AsyncSession, name: str, code: str, exclude_id: UUID | None = None) -> Branch | None:
        q = select(Branch).where((Branch.name == name) | (Branch.code == code))
        if exclude_id:
            q = q.where(Branch.id != exclude_id)
        result = await db.execute(q)
        return result.scalars().first()

    async def count_other_active_main_stores(self, db: AsyncSession, exclude_id: UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(Branch).where(
                Branch.branch_type == "main_store",
                Branch.is_active == True,
                Branch.id != exclude_id,
            )
        )
        return result.scalar_one()

    async def get_history_counts(self, db: AsyncSession, branch_id: UUID) -> dict[str, int]:
        """Every FK reference to branches.id in the schema — none of them
        are ON DELETE SET NULL (confirmed by inspecting every model that
        references branches.id), so a hard delete is only safe when every
        one of these is zero. Mirrors user_repo.get_history_counts's
        established pattern for the same kind of decision on users."""
        from app.models.user import User
        from app.models.inventory import Inventory
        from app.models.inventory_transaction import InventoryTransaction
        from app.models.sale import Sale
        from app.models.stock_request import StockRequest
        from app.models.stock_transfer import StockTransfer
        from app.models.daily_closing import DailyClosing
        from app.models.audit_log import AuditLog

        async def count(stmt) -> int:
            return (await db.execute(stmt)).scalar_one()

        return {
            "users_assigned": await count(
                select(func.count()).select_from(User).where(User.branch_id == branch_id)
            ),
            "inventory_records": await count(
                select(func.count()).select_from(Inventory).where(Inventory.branch_id == branch_id)
            ),
            "inventory_transactions": await count(
                select(func.count()).select_from(InventoryTransaction).where(InventoryTransaction.branch_id == branch_id)
            ),
            "sales": await count(
                select(func.count()).select_from(Sale).where(Sale.branch_id == branch_id)
            ),
            "stock_requests": await count(
                select(func.count()).select_from(StockRequest).where(
                    (StockRequest.from_branch_id == branch_id) | (StockRequest.to_branch_id == branch_id)
                )
            ),
            "stock_transfers": await count(
                select(func.count()).select_from(StockTransfer).where(
                    (StockTransfer.from_branch_id == branch_id) | (StockTransfer.to_branch_id == branch_id)
                )
            ),
            "daily_closings": await count(
                select(func.count()).select_from(DailyClosing).where(DailyClosing.branch_id == branch_id)
            ),
            "audit_logs": await count(
                select(func.count()).select_from(AuditLog).where(
                    ((AuditLog.branch_id == branch_id) | (AuditLog.to_branch_id == branch_id)),
                    AuditLog.action.notin_(BRANCH_LIFECYCLE_ACTIONS),
                )
            ),
        }

    async def hard_delete(self, db: AsyncSession, branch_id: UUID) -> None:
        """Only ever called once get_history_counts has confirmed zero real
        business activity. The branch's own lifecycle audit rows (its
        BRANCH_CREATED, any BRANCH_UPDATED) are deliberately not counted as
        blocking history, but they still hold a real FK to this row — detach
        them (keep the row, just null the reference; entity_id/details keep
        the record's identity in the audit trail) so the delete below
        doesn't hit that FK."""
        from app.models.audit_log import AuditLog

        await db.execute(
            update(AuditLog)
            .where(AuditLog.branch_id == branch_id, AuditLog.action.in_(BRANCH_LIFECYCLE_ACTIONS))
            .values(branch_id=None)
        )
        await db.execute(delete(Branch).where(Branch.id == branch_id))


branch_repo = BranchRepository()
