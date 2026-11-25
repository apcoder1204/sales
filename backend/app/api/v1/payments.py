from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customers import require_customer_reader
from app.db.session import get_db
from app.schemas.payment import PaymentOut, PaymentReceipt
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
