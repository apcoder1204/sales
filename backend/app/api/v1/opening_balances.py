from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import branch_context
from app.core.dependencies import require_admin, require_role
from app.core.idempotency import get_cached_response, store_response
from app.db.session import get_db
from app.schemas.payment import (
    OpeningBalanceCancel, OpeningBalanceDecision, OpeningBalanceOut, OpeningBalanceReject,
)
from app.services import opening_balance_service

router = APIRouter(prefix="/opening-balances", tags=["Opening balances"])

_APPROVE_IDEMPOTENCY_ENDPOINT = "POST /opening-balances/approve"


@router.get("", response_model=list[OpeningBalanceOut])
async def list_opening_balances(
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = None,
    branch_id: UUID | None = Depends(branch_context),  # a cashier sees only their branch
    current_user=Depends(require_role("super_admin", "admin", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    rows = await opening_balance_service.list_(db, status, branch_id)
    return [opening_balance_service.to_out(ob) for ob in rows]


@router.post("/{ob_id}/approve", response_model=OpeningBalanceOut)
async def approve_opening_balance(
    ob_id: UUID,
    data: OpeningBalanceDecision,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cached = await get_cached_response(
        db, current_user.id, _APPROVE_IDEMPOTENCY_ENDPOINT, idempotency_key
    )
    if cached is not None:
        status_code, body = cached
        return JSONResponse(status_code=status_code, content=body)
    ob = await opening_balance_service.approve(db, ob_id, current_user, data.note)
    body = opening_balance_service.to_out(ob).model_dump(mode="json")
    await store_response(
        db, current_user.id, _APPROVE_IDEMPOTENCY_ENDPOINT, idempotency_key, 200, body
    )
    return body


@router.post("/{ob_id}/reject", response_model=OpeningBalanceOut)
async def reject_opening_balance(
    ob_id: UUID,
    data: OpeningBalanceReject,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ob = await opening_balance_service.reject(db, ob_id, current_user, data.note)
    return opening_balance_service.to_out(ob)


@router.post("/{ob_id}/cancel", response_model=OpeningBalanceOut)
async def cancel_opening_balance(
    ob_id: UUID,
    data: OpeningBalanceCancel,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ob = await opening_balance_service.cancel(db, ob_id, current_user, data.reason)
    return opening_balance_service.to_out(ob)
