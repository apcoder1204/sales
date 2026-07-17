from uuid import UUID
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

UTC = timezone.utc

from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.branch import Branch
from app.models.user import User
from app.schemas.report import (
    SalesReportResponse, SalesSummary, ChartPoint, TopProduct,
    PaymentBreakdown, InventoryReportResponse, InventorySummary,
    BranchInventory, LowStockItem, BranchPerformanceResponse,
    BranchPerformance, CashierPerformanceResponse, CashierPerformance,
    ClosingReportResponse, ClosingReportRow, ClosingReportSummary
)
from app.repositories.inventory_repo import inventory_repo


def _get_date_range(period: str, from_date: date | None, to_date: date | None):
    today = datetime.now().date()
    if period == "today":
        return (
            datetime.combine(today, datetime.min.time()),
            datetime.combine(today, datetime.max.time()),
        )
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return (
            datetime.combine(start, datetime.min.time()),
            datetime.combine(today, datetime.max.time()),
        )
    elif period == "month":
        start = today.replace(day=1)
        return (
            datetime.combine(start, datetime.min.time()),
            datetime.combine(today, datetime.max.time()),
        )
    else:
        return (
            datetime.combine(from_date or today, datetime.min.time()),
            datetime.combine(to_date or today, datetime.max.time()),
        )


class ReportService:
    async def get_sales_report(
        self, db: AsyncSession,
        period: str, from_date: date | None, to_date: date | None,
        branch_id: UUID | None
    ) -> SalesReportResponse:
        from_dt, to_dt = _get_date_range(period, from_date, to_date)

        summary_q = select(
            func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"),
            func.count(Sale.id).label("count"),
            func.coalesce(func.avg(Sale.total_amount), 0).label("avg"),
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        )
        if branch_id:
            summary_q = summary_q.where(Sale.branch_id == branch_id)
        sr = (await db.execute(summary_q)).mappings().one()

        items_q = select(func.coalesce(func.sum(SaleItem.quantity), 0)).join(
            Sale, SaleItem.sale_id == Sale.id
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        )
        if branch_id:
            items_q = items_q.where(Sale.branch_id == branch_id)
        total_items = (await db.execute(items_q)).scalar_one()

        chart_q = select(
            func.date_trunc("day", Sale.created_at).label("day"),
            func.sum(Sale.total_amount).label("total"),
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ).group_by("day").order_by("day")
        if branch_id:
            chart_q = chart_q.where(Sale.branch_id == branch_id)
        chart_rows = (await db.execute(chart_q)).all()
        chart_data = [
            ChartPoint(label=r.day.strftime("%d %b"), value=float(r.total or 0))
            for r in chart_rows
        ]

        top_q = select(
            Product.name,
            func.sum(SaleItem.quantity).label("qty"),
            func.sum(SaleItem.line_total).label("rev"),
        ).join(SaleItem, Product.id == SaleItem.product_id).join(
            Sale, SaleItem.sale_id == Sale.id
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ).group_by(Product.name).order_by(func.sum(SaleItem.line_total).desc()).limit(10)
        if branch_id:
            top_q = top_q.where(Sale.branch_id == branch_id)
        top_rows = (await db.execute(top_q)).all()
        top_products = [
            TopProduct(product=r.name, qty_sold=int(r.qty or 0), revenue=float(r.rev or 0))
            for r in top_rows
        ]

        pay_q = select(
            Sale.payment_method,
            func.count(Sale.id).label("cnt"),
            func.sum(Sale.total_amount).label("total"),
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ).group_by(Sale.payment_method)
        if branch_id:
            pay_q = pay_q.where(Sale.branch_id == branch_id)
        pay_rows = (await db.execute(pay_q)).all()
        payment_breakdown = [
            PaymentBreakdown(
                method=r.payment_method.replace("_", " ").title(),
                count=int(r.cnt),
                total=float(r.total or 0),
            ) for r in pay_rows
        ]

        return SalesReportResponse(
            summary=SalesSummary(
                total_revenue=float(sr["revenue"]),
                total_transactions=int(sr["count"]),
                avg_transaction=float(sr["avg"]),
                total_items_sold=int(total_items),
            ),
            chart_data=chart_data,
            top_products=top_products,
            payment_breakdown=payment_breakdown,
            generated_at=datetime.now(UTC),
        )

    async def get_inventory_report(
        self, db: AsyncSession, branch_id: UUID | None
    ) -> InventoryReportResponse:
        q = select(
            func.count(func.distinct(Inventory.product_id)).label("products"),
            func.coalesce(func.sum(Inventory.quantity), 0).label("qty"),
            func.coalesce(func.sum(Inventory.quantity * Product.cost_price), 0).label("value"),
        ).join(Product, Inventory.product_id == Product.id).where(Product.status == "active")
        if branch_id:
            q = q.where(Inventory.branch_id == branch_id)
        sr = (await db.execute(q)).mappings().one()

        low_stock_items = await inventory_repo.get_low_stock(db, branch_id)
        by_branch_q = select(
            Branch.name,
            func.coalesce(func.sum(Inventory.quantity), 0).label("qty"),
            func.coalesce(func.sum(Inventory.quantity * Product.cost_price), 0).label("value"),
        ).join(Inventory, Branch.id == Inventory.branch_id).join(
            Product, Inventory.product_id == Product.id
        ).where(Product.status == "active", Branch.is_active == True).group_by(Branch.name)
        if branch_id:
            by_branch_q = by_branch_q.where(Branch.id == branch_id)
        br_rows = (await db.execute(by_branch_q)).all()

        return InventoryReportResponse(
            summary=InventorySummary(
                total_products=int(sr["products"]),
                total_quantity=int(sr["qty"]),
                total_value=float(sr["value"]),
                low_stock_count=len(low_stock_items),
            ),
            by_branch=[
                BranchInventory(
                    branch=r.name,
                    total_quantity=int(r.qty),
                    total_value=float(r.value),
                    low_stock_count=0,
                ) for r in br_rows
            ],
            low_stock_items=[LowStockItem(**i) for i in low_stock_items],
            generated_at=datetime.now(UTC),
        )

    async def get_branch_performance(
        self, db: AsyncSession,
        period: str, from_date: date | None, to_date: date | None
    ) -> BranchPerformanceResponse:
        from_dt, to_dt = _get_date_range(period, from_date, to_date)
        q = select(
            Branch.name,
            func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"),
            func.count(Sale.id).label("count"),
            func.coalesce(func.avg(Sale.total_amount), 0).label("avg"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("items"),
        ).join(Sale, Branch.id == Sale.branch_id).join(
            SaleItem, Sale.id == SaleItem.sale_id
        ).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ).group_by(Branch.name).order_by(func.sum(Sale.total_amount).desc())
        rows = (await db.execute(q)).all()
        branches = [
            BranchPerformance(
                branch=r.name,
                total_revenue=float(r.revenue),
                transaction_count=int(r.count),
                avg_transaction=float(r.avg),
                items_sold=int(r.items),
            ) for r in rows
        ]
        chart_data = [ChartPoint(label=b.branch, value=b.total_revenue) for b in branches]
        return BranchPerformanceResponse(branches=branches, chart_data=chart_data, generated_at=datetime.now(UTC))

    async def get_cashier_performance(
        self, db: AsyncSession,
        branch_id: UUID | None,
        period: str, from_date: date | None, to_date: date | None
    ) -> CashierPerformanceResponse:
        from_dt, to_dt = _get_date_range(period, from_date, to_date)
        q = select(
            User.full_name,
            Branch.name.label("branch"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("revenue"),
            func.count(Sale.id).label("count"),
            func.coalesce(func.avg(Sale.total_amount), 0).label("avg"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("items"),
        ).join(Sale, User.id == Sale.cashier_id).join(
            Branch, Sale.branch_id == Branch.id
        ).join(SaleItem, Sale.id == SaleItem.sale_id).where(
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ).group_by(User.full_name, Branch.name).order_by(func.sum(Sale.total_amount).desc())
        if branch_id:
            q = q.where(Sale.branch_id == branch_id)
        rows = (await db.execute(q)).all()
        cashiers = [
            CashierPerformance(
                cashier=r.full_name,
                branch=r.branch,
                total_revenue=float(r.revenue),
                transaction_count=int(r.count),
                avg_transaction=float(r.avg),
                items_sold=int(r.items),
            ) for r in rows
        ]
        return CashierPerformanceResponse(cashiers=cashiers, generated_at=datetime.now(UTC))

    async def get_closing_report(
        self, db: AsyncSession,
        period: str, from_date: date | None, to_date: date | None,
        branch_id: UUID | None
    ) -> ClosingReportResponse:
        from app.models.daily_closing import DailyClosing
        from_dt, to_dt = _get_date_range(period, from_date, to_date)

        q = select(DailyClosing).where(
            DailyClosing.business_date >= from_dt.date(),
            DailyClosing.business_date <= to_dt.date(),
        )
        if branch_id:
            q = q.where(DailyClosing.branch_id == branch_id)
        rows = (await db.execute(q.order_by(DailyClosing.business_date.desc()))).scalars().all()

        closings = [
            ClosingReportRow(
                business_date=c.business_date, branch=c.branch.name, status=c.status,
                total_cash=float(c.total_cash), total_mobile_money=float(c.total_mobile_money),
                total_bank_transfer=float(c.total_bank_transfer), total_revenue=float(c.total_revenue),
                cash_variance=float(c.cash_variance) if c.cash_variance is not None else None,
                total_expenses=float(sum((e.amount for e in c.expenses), Decimal("0"))),
                closed_by=c.closer.full_name if c.closer else None,
            ) for c in rows
        ]
        summary = ClosingReportSummary(
            total_cash=sum(c.total_cash for c in closings),
            total_mobile_money=sum(c.total_mobile_money for c in closings),
            total_bank_transfer=sum(c.total_bank_transfer for c in closings),
            total_revenue=sum(c.total_revenue for c in closings),
            closings_count=len(closings),
        )
        return ClosingReportResponse(summary=summary, closings=closings, generated_at=datetime.now(UTC))


report_service = ReportService()
