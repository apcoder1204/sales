from uuid import UUID
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import require_role
from app.core.authorization import resolve_read_branch_id
from app.services.report_service import report_service
from app.repositories.inventory_repo import inventory_repo

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

router = APIRouter(prefix="/reports", tags=["Ripoti"])

_financial_access = Depends(require_role("super_admin", "admin", "general_manager"))


@router.get("/dashboard")
async def dashboard_summary(
    branch_id: UUID | None = None,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "store_keeper", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select, and_, or_
    from datetime import datetime, timedelta
    from app.models.sale import Sale
    from app.models.product import Product
    from app.models.inventory import Inventory
    from app.models.stock_request import StockRequest
    from app.models.branch import Branch

    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    is_global = current_user.role.name in ("super_admin", "admin", "general_manager")
    if not is_global:
        scoped_branch_id = current_user.branch_id
    else:
        scoped_branch_id = branch_id

    sale_branch_filter = [Sale.branch_id == scoped_branch_id] if scoped_branch_id else []
    inv_branch_filter = [Inventory.branch_id == scoped_branch_id] if scoped_branch_id else []

    today_rev = (await db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
            Sale.status == "completed", Sale.created_at >= today_start, *sale_branch_filter
        )
    )).scalar_one()

    month_rev = (await db.execute(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
            Sale.status == "completed", Sale.created_at >= month_start, *sale_branch_filter
        )
    )).scalar_one()

    today_tx = (await db.execute(
        select(func.count(Sale.id)).where(
            Sale.status == "completed", Sale.created_at >= today_start, *sale_branch_filter
        )
    )).scalar_one()

    from app.models.sale_item import SaleItem
    today_items_sold = (await db.execute(
        select(func.coalesce(func.sum(SaleItem.quantity), 0))
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(Sale.status == "completed", Sale.created_at >= today_start, *sale_branch_filter)
    )).scalar_one()

    total_products = (await db.execute(select(func.count(Product.id)).where(Product.status == "active"))).scalar_one()

    low_stock_q = select(func.count()).select_from(Inventory).where(Inventory.quantity - Inventory.reserved_qty <= 5)
    if inv_branch_filter:
        low_stock_q = low_stock_q.where(*inv_branch_filter)
    low_stock_count = (await db.execute(low_stock_q)).scalar_one()

    pending_q = select(func.count(StockRequest.id)).where(StockRequest.status == "pending")
    if scoped_branch_id:
        pending_q = pending_q.where(
            or_(
                StockRequest.from_branch_id == scoped_branch_id,
                StockRequest.to_branch_id == scoped_branch_id,
            )
        )
    pending_requests = (await db.execute(pending_q)).scalar_one()

    inv_value_q = (
        select(func.coalesce(func.sum(Inventory.quantity * Product.cost_price), 0))
        .join(Product, Inventory.product_id == Product.id)
    )
    if inv_branch_filter:
        inv_value_q = inv_value_q.where(*inv_branch_filter)
    inventory_value = (await db.execute(inv_value_q)).scalar_one()

    trend = []
    for i in range(6, -1, -1):
        day = _utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        rev = (await db.execute(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                Sale.status == "completed",
                Sale.created_at >= day_start,
                Sale.created_at <= day_end,
                *sale_branch_filter,
            )
        )).scalar_one()
        trend.append({"label": day.strftime("%d/%m"), "total": float(rev)})

    recent_sales = []
    if current_user.role.name == "cashier":
        rows = (await db.execute(
            select(Sale).where(Sale.status == "completed", Sale.branch_id == current_user.branch_id)
            .order_by(Sale.created_at.desc()).limit(5)
        )).scalars().all()
        recent_sales = [
            {
                "id": str(s.id),
                "transaction_no": s.transaction_no,
                "total_amount": float(s.total_amount),
                "items_count": 0,
                "created_at": s.created_at.isoformat(),
            }
            for s in rows
        ]

    low_items_q = (
        select(Inventory, Product, Branch.name.label("branch_name"))
        .join(Product, Inventory.product_id == Product.id)
        .join(Branch, Inventory.branch_id == Branch.id)
        .where(Inventory.quantity - Inventory.reserved_qty <= 5)
    )
    if inv_branch_filter:
        low_items_q = low_items_q.where(*inv_branch_filter)
    low_items = (await db.execute(low_items_q.limit(10))).all()
    low_stock_items = [
        {
            "id": str(inv.id),
            "product_name": prod.name,
            "branch_name": branch_name,
            "available_qty": inv.quantity - inv.reserved_qty,
        }
        for inv, prod, branch_name in low_items
    ]

    branch_sales_q = (
        select(Branch.name.label("branch_name"), func.coalesce(func.sum(Sale.total_amount), 0).label("total_revenue"))
        .outerjoin(
            Sale,
            and_(Sale.branch_id == Branch.id, Sale.status == "completed", Sale.created_at >= month_start),
        )
        .group_by(Branch.id, Branch.name)
    )
    if scoped_branch_id:
        branch_sales_q = branch_sales_q.where(Branch.id == scoped_branch_id)
    branch_sales = (await db.execute(branch_sales_q)).all()

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


@router.get("/inventory")
async def inventory_report(
    branch_id: UUID | None = None,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "store_keeper")),
    db: AsyncSession = Depends(get_db),
):
    branch_id = await resolve_read_branch_id(db, current_user, branch_id)
    return await report_service.get_inventory_report(db, branch_id)


@router.get("/branch-performance", dependencies=[_financial_access])
async def branch_performance(
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_branch_performance(db, period, from_date, to_date, branch_id)


@router.get("/cashier-performance", dependencies=[_financial_access])
async def cashier_performance(
    branch_id: UUID | None = None,
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await report_service.get_cashier_performance(db, branch_id, period, from_date, to_date)


@router.get("/closing")
async def closing_report(
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    # Cashiers (POS) can only pull their own branch's closing report — never
    # someone else's, regardless of what branch_id they pass.
    if current_user.role.name == "cashier":
        branch_id = current_user.branch_id
    return await report_service.get_closing_report(db, period, from_date, to_date, branch_id)


@router.get("/low-stock")
async def low_stock_report(
    branch_id: UUID | None = None,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "store_keeper")),
    db: AsyncSession = Depends(get_db),
):
    branch_id = await resolve_read_branch_id(db, current_user, branch_id)
    items = await inventory_repo.get_low_stock(db, branch_id)
    return {"items": items}
