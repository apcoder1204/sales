from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import require_role
from app.schemas.daily_closing import (
    ClosingPreviewResponse, ClosingResponse, CloseDayRequest, ReopenRequest
)
from app.core.exceptions import InsufficientPermissionException
from app.services.daily_closing_service import daily_closing_service

router = APIRouter(prefix="/closings", tags=["Ufungaji wa Siku"])


@router.get("/preview", response_model=ClosingPreviewResponse)
async def preview_closing(
    branch_id: UUID,
    business_date: date | None = None,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name == "cashier" and str(current_user.branch_id) != str(branch_id):
        raise InsufficientPermissionException("Huwezi kuona ufungaji wa tawi lingine")
    return await daily_closing_service.preview(db, branch_id, business_date)


@router.post("/close", response_model=ClosingResponse, status_code=201)
async def close_day(
    data: CloseDayRequest,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name == "cashier" and str(current_user.branch_id) != str(data.branch_id):
        raise InsufficientPermissionException("Huwezi kufunga siku ya tawi lingine")
    closing = await daily_closing_service.close_day(db, data, current_user)
    return daily_closing_service.serialize(closing)


@router.put("/{closing_id}/reopen", response_model=ClosingResponse)
async def reopen_closing(
    closing_id: UUID, data: ReopenRequest,
    current_user=Depends(require_role("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    closing = await daily_closing_service.reopen(db, closing_id, data.reason, current_user)
    return daily_closing_service.serialize(closing)


@router.get("")
async def list_closings(
    branch_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1, per_page: int = 20,
    current_user=Depends(require_role("super_admin", "admin", "general_manager", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name == "cashier":
        branch_id = current_user.branch_id
    return await daily_closing_service.list_closings(db, branch_id, from_date, to_date, page, per_page)
