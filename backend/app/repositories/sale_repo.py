from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.repositories.base import BaseRepository
from app.core.business_time import business_date_today


def credit_at_sale_expr():
    """Per-sale SQL expression: the part of the sale total not paid at the
    till (active kind='sale' allocations) — i.e. credit given on the sale."""
    paid_at_till = (
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.sale_id == Sale.id,
            Payment.kind == "sale", Payment.status == "active",
        )
        .scalar_subquery()
    )
    return Sale.total_amount - paid_at_till


class SaleRepository(BaseRepository[Sale]):
    model = Sale

    async def get_next_transaction_no(self, db: AsyncSession) -> str:
        result = await db.execute(text("SELECT nextval('seq_sale_number')"))
        seq = result.scalar()
        today = business_date_today().strftime("%Y%m%d")
        return f"TXN-{today}-{seq:04d}"

    async def create_sale(self, db: AsyncSession, data: dict) -> Sale:
        sale = Sale(**data)
        db.add(sale)
        await db.flush()
        return sale

    async def get_by_id_locked(self, db: AsyncSession, id: UUID) -> Sale | None:
        """Locks the Sale row so void can safely check-then-act on its
        status without racing a concurrent void of the same sale."""
        # FOR NO KEY UPDATE (key_share=True): still blocks a second void, but
        # doesn't conflict with the KEY SHARE lock a concurrent debt payment's
        # payment_allocations FK check takes on this sale — FOR UPDATE would
        # deadlock with it (void: sale → customer; payment: customer → sale).
        result = await db.execute(select(Sale).where(Sale.id == id).with_for_update(key_share=True))
        return result.scalar_one_or_none()

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
            q = q.where(
                select(PaymentAllocation.id)
                .join(Payment, Payment.id == PaymentAllocation.payment_id)
                .where(PaymentAllocation.sale_id == Sale.id, Payment.method == payment_method)
                .exists()
            )
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
        """Money actually received at a branch in a time window, per method —
        shared by end-of-day closing (preview + close). Method totals are
        active payments of both kinds (till + debt collections, spec §6.4);
        `count`/`revenue` are completed sales; `credit_given` is the part of
        those sales not paid at the till; `debt_collected` is debt payments."""
        in_window = (
            Payment.status == "active",
            Payment.branch_id == branch_id,
            Payment.created_at >= from_dt,
            Payment.created_at <= to_dt,
        )
        rows = (await db.execute(
            select(Payment.method, func.coalesce(func.sum(Payment.amount), 0).label("total"))
            .where(*in_window).group_by(Payment.method)
        )).all()
        totals = {"cash": 0, "mobile_money": 0, "bank_transfer": 0}
        for r in rows:
            totals[r.method] = float(r.total or 0)

        sale_window = (
            Sale.status == "completed",
            Sale.branch_id == branch_id,
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        )
        count, revenue = (await db.execute(
            select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_amount), 0))
            .where(*sale_window)
        )).one()
        credit_given = (await db.execute(
            select(func.coalesce(func.sum(credit_at_sale_expr()), 0)).where(*sale_window)
        )).scalar()
        debt_collected = (await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(*in_window, Payment.kind == "debt")
        )).scalar()
        return {
            **totals, "count": int(count), "revenue": float(revenue or 0),
            "credit_given": float(credit_given or 0), "debt_collected": float(debt_collected or 0),
        }

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
