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
from app.core.authorization import branch_context
from app.core.exceptions import InsufficientPermissionException

router = APIRouter(prefix="/inventory", tags=["Hifadhi"])

_keeper = Depends(require_role("super_admin", "admin", "store_keeper", "general_manager"))
# Every role except cashier/store_keeper/global-scope is nonexistent in this
# app's role set, so gating on the union of both is equivalent to (and
# replaces) the old "everyone except these 5 named roles" 403 fallback.
_inventory_reader = Depends(require_role("super_admin", "admin", "general_manager", "store_keeper", "cashier"))


@router.get("")
async def list_inventory(
    branch_id: UUID | None = Depends(branch_context),
    low_stock: bool = False,
    category_id: int | None = None,
    page: int = 1, per_page: int = 20,
    current_user=_inventory_reader,
    db: AsyncSession = Depends(get_db),
):
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
    branch_id: UUID | None = Depends(branch_context),
    product_id: UUID | None = None,
    tx_type: str | None = None,
    page: int = 1, per_page: int = 20,
    current_user=_inventory_reader,
    db: AsyncSession = Depends(get_db),
):
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
    current_user=Depends(require_role(
        "super_admin", "admin", "general_manager", "store_keeper", "cashier"
    )),
    db: AsyncSession = Depends(get_db),
):
    # A cashier may only ask "what can supply MY branch" — not probe another
    # branch's sourcing options. store_keeper/admin/general_manager/super_admin
    # legitimately need to check sourcing for any destination while
    # allocating/approving requests, so they're left unrestricted here.
    if current_user.role.name == "cashier" and str(current_user.branch_id) != str(destination_branch_id):
        raise InsufficientPermissionException("Huwezi kuona vyanzo vya tawi lingine")
    return await inventory_service.get_available_sources(db, product_id, quantity, destination_branch_id)


@router.get("/low-stock")
async def get_low_stock(
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    return await inventory_repo.get_low_stock(db, branch_id)
