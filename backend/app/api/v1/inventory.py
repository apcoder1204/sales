from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.schemas.inventory import (
    StockAdjustRequest, InventoryMovementResponse,
    AvailableSourcesResponse
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.inventory_service import inventory_service
from app.repositories.inventory_repo import inventory_repo

router = APIRouter(prefix="/inventory", tags=["Hifadhi"])

_keeper = Depends(require_role("super_admin", "admin", "store_keeper", "general_manager"))


@router.get("")
async def list_inventory(
    branch_id: UUID | None = None,
    low_stock: bool = False,
    category_id: int | None = None,
    page: int = 1, per_page: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current_user.role.name
    # Branch-scoped roles always see only their own branch
    if role in ("cashier", "store_keeper"):
        branch_id = current_user.branch_id
    elif role not in ("super_admin", "admin", "general_manager"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Huna ruhusa ya kuona hifadhi")
    return await inventory_service.get_inventory_list(db, branch_id, low_stock, page, per_page)


@router.post("/adjust", response_model=MessageResponse)
async def adjust_stock(
    data: StockAdjustRequest,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper")),
    db: AsyncSession = Depends(get_db),
):
    await inventory_service.adjust_stock(
        db, data.product_id, data.branch_id, data.quantity, data.type, data.notes, current_user
    )
    return {"message": "Hisa imesasishwa"}


@router.get("/movements")
async def list_movements(
    branch_id: UUID | None = None,
    product_id: UUID | None = None,
    tx_type: str | None = None,
    page: int = 1, per_page: int = 20,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name in ("store_keeper", "cashier"):
        branch_id = current_user.branch_id
    skip = (page - 1) * per_page
    import math
    rows, total = await inventory_repo.get_movements(db, branch_id, product_id, tx_type, skip, per_page)
    items = [
        InventoryMovementResponse(
            id=r.id,
            product=r.product.name,
            product_code=r.product.product_code,
            branch=r.branch.name,
            transaction_type=r.transaction_type,
            quantity_before=r.quantity_before,
            quantity_change=r.quantity_change,
            quantity_after=r.quantity_after,
            reference_type=r.reference_type,
            notes=r.notes,
            performed_by=r.performer.full_name,
            created_at=r.created_at,
        ) for r in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": math.ceil(total / per_page) if total else 1}


@router.get("/available-sources", response_model=AvailableSourcesResponse)
async def get_available_sources(
    product_id: UUID,
    quantity: int,
    destination_branch_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_service.get_available_sources(db, product_id, quantity, destination_branch_id)


@router.get("/low-stock")
async def get_low_stock(
    branch_id: UUID | None = None,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name == "store_keeper" and not branch_id:
        branch_id = current_user.branch_id
    return await inventory_repo.get_low_stock(db, branch_id)
