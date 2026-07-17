from uuid import UUID
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import require_role
from app.services.report_service import report_service
from app.repositories.inventory_repo import inventory_repo

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

router = APIRouter(prefix="/reports", tags=["Ripoti"])

_report_access = Depends(require_role("super_admin", "admin", "general_manager", "store_keeper"))
_financial_access = Depends(require_role("super_admin", "admin", "general_manager"))


@router.get("/dashboard")
async def dashboard_summary(
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "store_keeper", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select, and_
    from datetime import datetime
    from app.models.sale import Sale
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.stock_request import StockRequest
    from app.models.branch import Branch

    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    branch_filter = [] if current_user.role.name in ("super_admin", "admin", "general_manager") else [Sale.branch_id == current_user.branch_id]

    today_rev = (await db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.status == "completed", Sale.created_at >= today_start, *branch_filter)
    )).scalar_one()

    month_rev = (await db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.status == "completed", Sale.created_at >= month_start, *branch_filter)
    )).scalar_one()

    today_tx = (await db.execute(
        select(func.count(Sale.id)).where(Sale.status == "completed", Sale.created_at >= today_start, *branch_filter)
    )).scalar_one()

    from app.models.sale_item import SaleItem
    today_items_sold = (await db.execute(
        select(func.coalesce(func.sum(SaleItem.quantity), 0))
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(Sale.status == "completed", Sale.created_at >= today_start, *branch_filter)
    )).scalar_one()

    total_products = (await db.execute(select(func.count(Product.id)).where(Product.status == "active"))).scalar_one()

    low_stock_count = (await db.execute(
        select(func.count()).select_from(Inventory).where(Inventory.quantity - Inventory.reserved_qty <= 5)
    )).scalar_one()

    pending_requests = (await db.execute(
        select(func.count(StockRequest.id)).where(StockRequest.status == "pending")
    )).scalar_one()

    inventory_value = (await db.execute(
        select(func.coalesce(func.sum(Inventory.quantity * Product.cost_price), 0))
        .join(Product, Inventory.product_id == Product.id)
    )).scalar_one()

    # Trend: last 7 days
    trend = []
    for i in range(6, -1, -1):
        from datetime import timedelta
        day = _utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        rev = (await db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                Sale.status == "completed", Sale.created_at >= day_start, Sale.created_at <= day_end, *branch_filter
            )
        )).scalar_one()
        trend.append({"label": day.strftime("%d/%m"), "total": float(rev)})

    # Recent sales for cashier
    recent_sales = []
    if current_user.role.name == "cashier":
        rows = (await db.execute(
            select(Sale).where(Sale.status == "completed", Sale.branch_id == current_user.branch_id)
            .order_by(Sale.created_at.desc()).limit(5)
        )).scalars().all()
        recent_sales = [{"id": str(s.id), "transaction_no": s.transaction_no, "total_amount": float(s.total_amount), "items_count": 0, "created_at": s.created_at.isoformat()} for s in rows]

    # Low stock items
    low_items = (await db.execute(
        select(Inventory, Product).join(Product, Inventory.product_id == Product.id)
        .where(Inventory.quantity - Inventory.reserved_qty <= 5).limit(10)
    )).all()
    low_stock_items = [{"id": str(inv.id), "product_name": prod.name, "branch_name": "", "available_qty": inv.quantity - inv.reserved_qty} for inv, prod in low_items]

    # Branch sales
    branch_sales = (await db.execute(
        select(Branch.name.label("branch_name"), func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"))
        .outerjoin(Sale, and_(Sale.branch_id == Branch.id, Sale.status == "completed", Sale.created_at >= month_start))
        .group_by(Branch.id, Branch.name)
    )).all()

    avg_sale_value = float(today_rev) / today_tx if today_tx > 0 else 0

    return {
        "today_revenue": float(today_rev),
        "month_revenue": float(month_rev),
        "today_transactions": today_tx,
        "today_items_sold": int(today_items_sold),
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "pending_requests": pending_requests,
        "inventory_value": float(inventory_value),
        "avg_sale_value": avg_sale_value,
        "sales_trend": trend,
        "branch_sales": [{"branch_name": r.branch_name, "total_revenue": float(r.total_revenue)} for r in branch_sales],
        "low_stock_items": low_stock_items,
        "recent_sales": recent_sales,
    }


@router.get("/sales", dependencies=[_financial_access])
async def sales_report(
    period: str = "today",
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_sales_report(db, period, from_date, to_date, branch_id)


@router.get("/inventory", dependencies=[_report_access])
async def inventory_report(
    branch_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_inventory_report(db, branch_id)


@router.get("/branch-performance", dependencies=[_financial_access])
async def branch_performance(
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_branch_performance(db, period, from_date, to_date)


@router.get("/cashier-performance", dependencies=[_financial_access])
async def cashier_performance(
    branch_id: UUID | None = None,
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_cashier_performance(db, branch_id, period, from_date, to_date)


@router.get("/closing", dependencies=[_financial_access])
async def closing_report(
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_closing_report(db, period, from_date, to_date, branch_id)


@router.get("/low-stock", dependencies=[_report_access])
async def low_stock_report(
    branch_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    items = await inventory_repo.get_low_stock(db, branch_id)
    return {"items": items}
