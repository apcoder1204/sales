from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.schemas.transfer import (
    StockRequestCreate, StockRequestReview, StockRequestApprovalRequest, DirectTransferCreate,
    StockRequestResponse, StockTransferResponse, TransferItemResponse
)
from app.schemas.common import MessageResponse
from app.services.transfer_service import transfer_service

router = APIRouter(prefix="/transfers", tags=["Uhamisho wa Bidhaa"])


@router.get("/requests")
async def list_requests(
    status: str | None = None,
    branch_id: UUID | None = None,
    page: int = 1, per_page: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Scope branch-level users to only their own branch's requests
    if current_user.role.name in ("cashier", "store_keeper"):
        branch_id = current_user.branch_id
    return await transfer_service.list_requests(db, status, branch_id, page, per_page)


@router.post("/requests", status_code=201)
async def create_request(
    data: StockRequestCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    req = await transfer_service.create_request(db, data, current_user)
    return transfer_service.serialize_request(req)


@router.put("/requests/{req_id}/approve", response_model=MessageResponse)
async def approve_request(
    req_id: UUID, data: StockRequestApprovalRequest,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    await transfer_service.approve_request(db, req_id, data, current_user)
    return {"message": "Ombi limeidhinishwa"}


@router.put("/requests/{req_id}/reject", response_model=MessageResponse)
async def reject_request(
    req_id: UUID, data: StockRequestReview,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    await transfer_service.reject_request(db, req_id, data.notes, current_user)
    return {"message": "Ombi limekataliwa"}


@router.post("/requests/{req_id}/execute", response_model=MessageResponse)
async def execute_request(
    req_id: UUID,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    await transfer_service.execute_request(db, req_id, current_user)
    return {"message": "Uhamisho umetekelezwa"}


@router.get("")
async def list_transfers(
    from_branch_id: UUID | None = None,
    to_branch_id: UUID | None = None,
    page: int = 1, per_page: int = 20,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    return await transfer_service.list_transfers(db, from_branch_id, to_branch_id, page, per_page)


@router.post("", status_code=201)
async def create_transfer(
    data: DirectTransferCreate,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    tf = await transfer_service.execute_transfer(db, data, current_user)
    return _fmt_transfer(tf)


def _fmt_transfer(tf) -> dict:
    return {
        "id": tf.id, "transfer_no": tf.transfer_no,
        "from_branch": tf.from_branch.name, "from_branch_id": tf.from_branch_id,
        "to_branch": tf.to_branch.name, "to_branch_id": tf.to_branch_id,
        "transferred_by": tf.executor.full_name,
        "status": tf.status, "notes": tf.notes,
        "items": [
            {"product": i.product.name, "product_id": i.product_id,
             "quantity": i.quantity, "unit_cost": i.unit_cost}
            for i in tf.items
        ],
        "created_at": tf.created_at, "completed_at": tf.completed_at,
    }
