from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customers import require_customer_reader
from app.core.dependencies import require_admin
from app.core.idempotency import get_cached_response, store_response
from app.db.session import get_db
from app.schemas.payment import PaymentOut, PaymentReceipt, PaymentReverseRequest
from app.services import payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(
    payment_id: UUID,
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.get_payment_for_viewing(db, payment_id, current_user)
    return (await payment_service.payments_out(db, [payment]))[0]


@router.get("/{payment_id}/receipt", response_model=PaymentReceipt)
async def get_payment_receipt(
    payment_id: UUID,
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.get_payment_for_viewing(db, payment_id, current_user)
    return await payment_service.build_receipt(db, payment)


_REVERSE_IDEMPOTENCY_ENDPOINT = "POST /payments/reverse"


@router.post("/{payment_id}/reverse", response_model=PaymentOut)
async def reverse_payment(
    payment_id: UUID,
    data: PaymentReverseRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cached = await get_cached_response(
        db, current_user.id, _REVERSE_IDEMPOTENCY_ENDPOINT, idempotency_key
    )
    if cached is not None:
        status_code, body = cached
        return JSONResponse(status_code=status_code, content=body)
    payment = await payment_service.reverse_payment(db, payment_id, data.reason, current_user)
    body = (await payment_service.payments_out(db, [payment]))[0].model_dump(mode="json")
    await store_response(
        db, current_user.id, _REVERSE_IDEMPOTENCY_ENDPOINT, idempotency_key, 200, body
    )
    return body
