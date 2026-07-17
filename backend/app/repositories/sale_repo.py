from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.repositories.base import BaseRepository


class SaleRepository(BaseRepository[Sale]):
    model = Sale

    async def get_next_transaction_no(self, db: AsyncSession) -> str:
        result = await db.execute(text("SELECT nextval('seq_sale_number')"))
        seq = result.scalar()
        today = datetime.now().strftime("%Y%m%d")
        return f"TXN-{today}-{seq:04d}"

    async def create_sale(self, db: AsyncSession, data: dict) -> Sale:
        sale = Sale(**data)
        db.add(sale)
        await db.flush()
        return sale

    async def create_sale_item(self, db: AsyncSession, data: dict) -> SaleItem:
        item = SaleItem(**data)
        db.add(item)
        await db.flush()
        return item

    async def list_sales(
        self, db: AsyncSession,
        branch_id: UUID | None = None,
        cashier_id: UUID | None = None,
        payment_method: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        skip: int = 0, limit: int = 20
    ) -> tuple[list[Sale], int]:
        q = select(Sale)
        if branch_id:
            q = q.where(Sale.branch_id == branch_id)
        if cashier_id:
            q = q.where(Sale.cashier_id == cashier_id)
        if payment_method:
            q = q.where(Sale.payment_method == payment_method)
        if from_date:
            q = q.where(Sale.created_at >= datetime.combine(from_date, datetime.min.time()))
        if to_date:
            q = q.where(Sale.created_at <= datetime.combine(to_date, datetime.max.time()))

        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await db.execute(
            q.order_by(Sale.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count

    async def get_totals_by_payment_method(
        self, db: AsyncSession,
        branch_id: UUID, from_dt: datetime, to_dt: datetime
    ) -> dict:
        """Aggregate completed-sale totals per payment method for a branch and
        time window — shared by the sales report's payment breakdown and by
        end-of-day closing (preview + close)."""
        q = select(
            Sale.payment_method,
            func.count(Sale.id).label("cnt"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("total"),
        ).where(
            Sale.status == "completed",
            Sale.branch_id == branch_id,
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ).group_by(Sale.payment_method)
        rows = (await db.execute(q)).all()
        totals = {"cash": 0, "mobile_money": 0, "bank_transfer": 0}
        count = 0
        revenue = 0
        for r in rows:
            totals[r.payment_method] = float(r.total or 0)
            count += int(r.cnt)
            revenue += float(r.total or 0)
        return {**totals, "count": count, "revenue": revenue}

    async def get_sales_summary(
        self, db: AsyncSession,
        from_dt: datetime, to_dt: datetime,
        branch_id: UUID | None = None
    ) -> dict:
        q = select(
            func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"),
            func.count(Sale.id).label("total_transactions"),
            func.coalesce(func.avg(Sale.total_amount), 0).label("avg_transaction"),
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        )
        if branch_id:
            q = q.where(Sale.branch_id == branch_id)
        result = await db.execute(q)
        return result.mappings().one()


sale_repo = SaleRepository()
