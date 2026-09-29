from uuid import UUID
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

UTC = timezone.utc

from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.product import Product
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.branch import Branch
from app.models.user import User
from app.models.daily_closing import DailyClosing
from app.schemas.report import (
    SalesReportResponse, SalesSummary, ChartPoint, TopProduct,
    PaymentBreakdown, InventoryReportResponse, InventorySummary,
    BranchInventory, LowStockItem, BranchPerformanceResponse,
    BranchPerformance, CashierPerformanceResponse, CashierPerformance,
    ClosingReportResponse, ClosingReportRow, ClosingReportSummary, ClosingReportExpense,
    ProfitLossResponse, ProfitLossPeriod, ProfitLossBranchInfo, ProfitLossSummary,
    BranchProfitLoss, ProductProfitability, CategoryProfitability,
)
from app.repositories.inventory_repo import inventory_repo
from app.core.business_time import business_date_today, utc_range_for_business_date
from app.config import settings


def _resolve_period_dates(period: str, from_date: date | None, to_date: date | None) -> tuple[date, date]:
    """The local (business) calendar start/end dates a period name refers
    to. Shared by _get_date_range (which converts this to a UTC datetime
    range for Sale.created_at filtering) and the P&L report (which also
    needs the plain local dates to filter DailyClosing.business_date
    directly, without a lossy round-trip through a UTC-shifted timestamp)."""
    today = business_date_today()
    if period == "today":
        return today, today
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == "month":
        return today.replace(day=1), today
    elif period == "last_month":
        first_this_month = today.replace(day=1)
        last_day_prev_month = first_this_month - timedelta(days=1)
        return last_day_prev_month.replace(day=1), last_day_prev_month
    else:
        return (from_date or today), (to_date or today)


def _get_date_range(period: str, from_date: date | None, to_date: date | None):
    # Sale.created_at is naive UTC; "today"/"week"/"month" are local (business)
    # calendar boundaries, so each endpoint must go through
    # utc_range_for_business_date rather than a raw UTC combine() — otherwise
    # the range is off by the local UTC offset and mis-attributes sales made
    # near local midnight, the same class of bug fixed in daily_closing_service.
    local_from, local_to = _resolve_period_dates(period, from_date, to_date)
    range_start, _ = utc_range_for_business_date(local_from)
    _, range_end = utc_range_for_business_date(local_to)
    return (range_start, range_end)


def _margin(numerator: Decimal, revenue: Decimal) -> float | None:
    """Gross/net margin % — null (not a divide-by-zero crash or a
    misleading 0%) when there's no revenue to take a percentage of."""
    if revenue == 0:
        return None
    return float(numerator / revenue * 100)


def _pl_status(net_profit: Decimal) -> str:
    if net_profit > 0:
        return "profit"
    if net_profit < 0:
        return "loss"
    return "break_even"


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

        # Group by local calendar day, not UTC calendar day: convert the
        # naive-UTC timestamp through the branch timezone before truncating,
        # so a sale just after local midnight isn't bucketed into the
        # previous day's chart point.
        local_created_at = func.timezone(settings.DEFAULT_TIMEZONE, func.timezone("UTC", Sale.created_at))
        chart_q = select(
            func.date_trunc("day", local_created_at).label("day"),
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
        period: str, from_date: date | None, to_date: date | None,
        branch_id: UUID | None = None,
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
        if branch_id:
            q = q.where(Branch.id == branch_id)
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
                expenses=[
                    ClosingReportExpense(description=e.description, amount=float(e.amount))
                    for e in c.expenses
                ],
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

    async def get_profit_loss_report(
        self, db: AsyncSession,
        period: str, from_date: date | None, to_date: date | None,
        branch_id: UUID | None,
    ) -> ProfitLossResponse:
        """Revenue and COGS come straight from SaleItem's own historical
        snapshot (unit_price/cost_price captured at sale time by
        sale_service.create_sale) — never Product's current price/cost, so
        a later cost change never retroactively changes a past period's
        profit. Operating expenses come from DailyClosingExpense, the app's
        one existing expense ledger — see _closing_counts_as_expense for why
        not every recorded "matumizi" line counts."""
        local_from, local_to = _resolve_period_dates(period, from_date, to_date)
        from_dt, to_dt = _get_date_range(period, from_date, to_date)

        item_filters = [
            Sale.status == "completed",
            Sale.created_at >= from_dt,
            Sale.created_at <= to_dt,
        ]
        if branch_id:
            item_filters.append(Sale.branch_id == branch_id)

        # ── Revenue / COGS by branch ────────────────────────────────────
        branch_sales_q = select(
            Branch.id, Branch.name,
            func.coalesce(func.sum(SaleItem.line_total), 0).label("revenue"),
            func.coalesce(func.sum(SaleItem.quantity * SaleItem.cost_price), 0).label("cogs"),
        ).select_from(SaleItem).join(Sale, SaleItem.sale_id == Sale.id).join(
            Branch, Sale.branch_id == Branch.id
        ).where(*item_filters).group_by(Branch.id, Branch.name)
        branch_sales_rows = (await db.execute(branch_sales_q)).all()

        # ── Operating expenses by branch ────────────────────────────────
        # A "matumizi" (DailyClosingExpense) row only represents a real cash
        # outflow when the register actually came up short — see
        # daily_closing_service.close_day's own comment: the identical
        # {description, amount} shape is also used to explain a SURPLUS
        # (e.g. a customer's unclaimed change), which is not a business
        # expense. Both counted_cash and total_cash are stored per closing,
        # so the raw (pre-matumizi) variance is exactly reconstructible —
        # no need to guess.
        closing_q = select(DailyClosing).where(
            DailyClosing.business_date >= local_from,
            DailyClosing.business_date <= local_to,
        )
        if branch_id:
            closing_q = closing_q.where(DailyClosing.branch_id == branch_id)
        closings = (await db.execute(closing_q)).scalars().all()

        def _closing_counts_as_expense(c: DailyClosing) -> bool:
            if c.counted_cash is None:
                return True
            return (c.counted_cash - c.total_cash) < 0

        branch_expenses: dict = defaultdict(lambda: Decimal("0"))
        branch_names: dict = {}
        for c in closings:
            branch_names.setdefault(c.branch_id, c.branch.name)
            if not _closing_counts_as_expense(c):
                continue
            branch_expenses[c.branch_id] += sum((e.amount for e in c.expenses), Decimal("0"))

        # ── Merge into one row per branch that had any activity ─────────
        branch_rows: dict = {}
        for r in branch_sales_rows:
            branch_rows[r.id] = {"name": r.name, "revenue": Decimal(r.revenue), "cogs": Decimal(r.cogs)}
        for bid, name in branch_names.items():
            branch_rows.setdefault(bid, {"name": name, "revenue": Decimal("0"), "cogs": Decimal("0")})

        branches: list[BranchProfitLoss] = []
        total_revenue = Decimal("0")
        total_cogs = Decimal("0")
        total_expenses = Decimal("0")
        for bid, row in sorted(branch_rows.items(), key=lambda kv: kv[1]["name"]):
            revenue, cogs = row["revenue"], row["cogs"]
            expenses = branch_expenses.get(bid, Decimal("0"))
            gross_profit = revenue - cogs
            net_profit = gross_profit - expenses
            branches.append(BranchProfitLoss(
                branch_id=bid, branch=row["name"],
                revenue=float(revenue), cost_of_goods_sold=float(cogs),
                gross_profit=float(gross_profit), gross_margin=_margin(gross_profit, revenue),
                operating_expenses=float(expenses), net_profit=float(net_profit),
                net_margin=_margin(net_profit, revenue), status=_pl_status(net_profit),
            ))
            total_revenue += revenue
            total_cogs += cogs
            total_expenses += expenses

        total_gross_profit = total_revenue - total_cogs
        total_net_profit = total_gross_profit - total_expenses
        summary = ProfitLossSummary(
            revenue=float(total_revenue), cost_of_goods_sold=float(total_cogs),
            gross_profit=float(total_gross_profit), gross_margin=_margin(total_gross_profit, total_revenue),
            operating_expenses=float(total_expenses), net_profit=float(total_net_profit),
            net_margin=_margin(total_net_profit, total_revenue), status=_pl_status(total_net_profit),
        )

        # ── Product profitability ───────────────────────────────────────
        product_q = select(
            Product.id, Product.name,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(SaleItem.line_total), 0).label("revenue"),
            func.coalesce(func.sum(SaleItem.quantity * SaleItem.cost_price), 0).label("cogs"),
        ).select_from(SaleItem).join(Sale, SaleItem.sale_id == Sale.id).join(
            Product, SaleItem.product_id == Product.id
        ).where(*item_filters).group_by(Product.id, Product.name)
        product_rows = (await db.execute(product_q)).all()
        products = sorted(
            (
                ProductProfitability(
                    product_id=r.id, product=r.name, quantity_sold=int(r.qty),
                    revenue=float(r.revenue), cost_of_goods_sold=float(r.cogs),
                    gross_profit=float(Decimal(r.revenue) - Decimal(r.cogs)),
                    gross_margin=_margin(Decimal(r.revenue) - Decimal(r.cogs), Decimal(r.revenue)),
                )
                for r in product_rows
            ),
            key=lambda p: p.gross_profit, reverse=True,
        )

        # ── Category profitability ──────────────────────────────────────
        category_q = select(
            Category.id, Category.name,
            func.coalesce(func.sum(SaleItem.line_total), 0).label("revenue"),
            func.coalesce(func.sum(SaleItem.quantity * SaleItem.cost_price), 0).label("cogs"),
        ).select_from(SaleItem).join(Sale, SaleItem.sale_id == Sale.id).join(
            Product, SaleItem.product_id == Product.id
        ).join(Category, Product.category_id == Category.id).where(*item_filters).group_by(
            Category.id, Category.name
        )
        category_rows = (await db.execute(category_q)).all()
        categories = sorted(
            (
                CategoryProfitability(
                    category_id=r.id, category=r.name,
                    revenue=float(r.revenue), cost_of_goods_sold=float(r.cogs),
                    gross_profit=float(Decimal(r.revenue) - Decimal(r.cogs)),
                    gross_margin=_margin(Decimal(r.revenue) - Decimal(r.cogs), Decimal(r.revenue)),
                )
                for r in category_rows
            ),
            key=lambda c: c.gross_profit, reverse=True,
        )

        branch_info = None
        if branch_id:
            b = await db.get(Branch, branch_id)
            if b:
                branch_info = ProfitLossBranchInfo(id=b.id, name=b.name)

        return ProfitLossResponse(
            period=ProfitLossPeriod(start=local_from, end=local_to),
            branch=branch_info,
            summary=summary,
            # Only meaningful as a breakdown in the consolidated ALL view —
            # a single already-scoped branch's list would just repeat itself.
            branches=branches if not branch_id else [],
            products=products,
            categories=categories,
            generated_at=datetime.now(UTC),
        )


report_service = ReportService()
