from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.models.product import Product
from app.models.category import Category
from app.models.inventory import Inventory
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    async def get_by_code(self, db: AsyncSession, code: str) -> Product | None:
        result = await db.execute(select(Product).where(Product.product_code == code))
        return result.scalar_one_or_none()

    async def list_products(
        self, db: AsyncSession,
        search: str | None = None,
        category_id: int | None = None,
        brand: str | None = None,
        status: str = "active",
        skip: int = 0, limit: int = 20,
        branch_id: UUID | None = None,
    ) -> tuple[list[Product], int, dict]:
        q = select(Product)
        if status:
            q = q.where(Product.status == status)
        if category_id:
            q = q.where(Product.category_id == category_id)
        if brand:
            q = q.where(Product.brand.ilike(f"%{brand}%"))
        if search:
            q = q.where(Product.name.ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar_one()
        rows = (await db.execute(q.order_by(Product.name).offset(skip).limit(limit))).scalars().all()

        stock_by_product: dict = {}
        if branch_id and rows:
            product_ids = [p.id for p in rows]
            inv_result = await db.execute(
                select(Inventory).where(
                    Inventory.branch_id == branch_id,
                    Inventory.product_id.in_(product_ids),
                )
            )
            for inv in inv_result.scalars().all():
                stock_by_product[inv.product_id] = inv

        return rows, total, stock_by_product

    async def get_next_code(self, db: AsyncSession) -> str:
        result = await db.execute(select(func.count()).select_from(Product))
        count = result.scalar_one()
        return f"PRD-{(count + 1):04d}"

    async def list_categories(self, db: AsyncSession) -> list[Category]:
        result = await db.execute(select(Category).order_by(Category.name))
        return result.scalars().all()


product_repo = ProductRepository()
