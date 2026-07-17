from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.branch import Branch
from app.models.product import Product
from app.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[Inventory]):
    model = Inventory

    async def get_by_product_branch(
        self, db: AsyncSession, product_id: UUID, branch_id: UUID
    ) -> Inventory | None:
        result = await db.execute(
            select(Inventory).where(
                Inventory.product_id == product_id,
                Inventory.branch_id == branch_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_product_branch_locked(
        self, db: AsyncSession, product_id: UUID, branch_id: UUID
    ) -> Inventory | None:
        result = await db.execute(
            select(Inventory)
            .where(Inventory.product_id == product_id, Inventory.branch_id == branch_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self, db: AsyncSession, product_id: UUID, branch_id: UUID
    ) -> Inventory:
        inv = await self.get_by_product_branch_locked(db, product_id, branch_id)
        if not inv:
            inv = await self.create(db, {
                "product_id": product_id,
                "branch_id": branch_id,
                "quantity": 0,
                "reserved_qty": 0,
            })
        return inv

    async def get_main_store(self, db: AsyncSession) -> Branch:
        result = await db.execute(
            select(Branch).where(Branch.branch_type == "main_store", Branch.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_available_sources(
        self, db: AsyncSession, product_id: UUID,
        requested_qty: int, exclude_branch_id: UUID
    ) -> list[dict]:
        result = await db.execute(
            select(Inventory, Branch)
            .join(Branch, Inventory.branch_id == Branch.id)
            .where(
                Inventory.product_id == product_id,
                Inventory.branch_id != exclude_branch_id,
                (Inventory.quantity - Inventory.reserved_qty) >= requested_qty,
                Branch.is_active == True,
            )
            .order_by((Inventory.quantity - Inventory.reserved_qty).desc())
        )
        rows = result.all()
        return [
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "branch_code": branch.code,
                "available_qty": inv.quantity - inv.reserved_qty,
            }
            for inv, branch in rows
        ]

    async def get_low_stock(
        self, db: AsyncSession, branch_id: UUID | None = None
    ) -> list[dict]:
        q = (
            select(Inventory, Product, Branch)
            .join(Product, Inventory.product_id == Product.id)
            .join(Branch, Inventory.branch_id == Branch.id)
            .where(
                Inventory.quantity <= Product.minimum_stock,
                Product.status == "active",
            )
        )
        if branch_id:
            q = q.where(Inventory.branch_id == branch_id)
        result = await db.execute(q.order_by(Inventory.quantity))
        return [
            {
                "product": p.name,
                "product_code": p.product_code,
                "branch": b.name,
                "current_stock": i.quantity,
                "minimum_stock": p.minimum_stock,
                "deficit": p.minimum_stock - i.quantity,
            }
            for i, p, b in result.all()
        ]

    async def get_movements(
        self, db: AsyncSession,
        branch_id: UUID | None = None,
        product_id: UUID | None = None,
        tx_type: str | None = None,
        skip: int = 0, limit: int = 20
    ) -> tuple[list[InventoryTransaction], int]:
        q = select(InventoryTransaction)
        if branch_id:
            q = q.where(InventoryTransaction.branch_id == branch_id)
        if product_id:
            q = q.where(InventoryTransaction.product_id == product_id)
        if tx_type:
            q = q.where(InventoryTransaction.transaction_type == tx_type)

        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await db.execute(
            q.order_by(InventoryTransaction.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count

    async def create_transaction(self, db: AsyncSession, data: dict) -> InventoryTransaction:
        tx = InventoryTransaction(**data)
        db.add(tx)
        await db.flush()
        return tx


inventory_repo = InventoryRepository()
