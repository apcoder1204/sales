import math
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import branch_context
from app.core.dependencies import get_current_user, require_admin, require_cashier_access, require_role
from app.core.idempotency import get_cached_response, store_response
from app.db.session import get_db
from app.schemas.customer import (
    CustomerCreate, CustomerCreditUpdate, CustomerDetailResponse, CustomerListItem, CustomerResponse,
    CustomerUpdate,
)
from app.schemas.payment import (
    DebtPaymentCreate, OpeningBalanceCreate, OpeningBalanceOut, PaymentOut, ReceivableOut,
)
from app.services import (
    customer_service, ledger_service, opening_balance_service, payment_service, statement_service,
)
from app.schemas.debt import StatementOut
from app.core.business_time import business_date_today
from datetime import date

router = APIRouter(prefix="/customers", tags=["Customers"])

# Everyone but store_keeper may look customers up (spec §6.5).
require_customer_reader = require_role("super_admin", "admin", "general_manager", "cashier")
# Old debts: the admin for any POS branch, a cashier for their own (the
# service pins the branch); deciding stays admin-only.
require_old_debt_enterer = require_role("super_admin", "admin", "cashier")


@router.get("")
async def list_customers(
    q: str | None = Query(None, max_length=100),
    status: Literal["active", "inactive"] | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await customer_service.search(db, q, status, page, per_page)
    items = []
    for c in rows:
        summary = await ledger_service.summary(db, c, branch_id)
        items.append(CustomerListItem(
            **CustomerResponse.model_validate(c).model_dump(), **summary.model_dump()
        ))
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": math.ceil(total / per_page) if total else 1}


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreate,
    current_user=Depends(require_cashier_access),
    db: AsyncSession = Depends(get_db),
):
    return await customer_service.create(db, data, current_user)


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: UUID,
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    return await customer_service.get_detail(db, customer_id, branch_id)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    current_user=Depends(require_cashier_access),
    db: AsyncSession = Depends(get_db),
):
    return await customer_service.update(db, customer_id, data, current_user)


@router.put("/{customer_id}/credit", response_model=CustomerResponse)
async def update_customer_credit(
    customer_id: UUID,
    data: CustomerCreditUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await customer_service.update_credit(db, customer_id, data, current_user)


_PAYMENT_IDEMPOTENCY_ENDPOINT = "POST /customers/payments"


@router.get("/{customer_id}/receivables", response_model=list[ReceivableOut])
async def list_receivables(
    customer_id: UUID,
    open_only: bool = True,
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    await customer_service.get_or_404(db, customer_id)
    rows = await ledger_service.receivables(db, customer_id, branch_id, open_only=open_only)
    return [ReceivableOut.model_validate(r) for r in rows]


@router.post("/{customer_id}/payments", response_model=PaymentOut, status_code=201)
async def record_payment(
    customer_id: UUID,
    data: DebtPaymentCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user=Depends(require_cashier_access),
    db: AsyncSession = Depends(get_db),
):
    cached = await get_cached_response(
        db, current_user.id, _PAYMENT_IDEMPOTENCY_ENDPOINT, idempotency_key
    )
    if cached is not None:
        status_code, body = cached
        return JSONResponse(status_code=status_code, content=body)
    payment = await payment_service.record_debt_payment(db, customer_id, data, current_user)
    body = (await payment_service.payments_out(db, [payment]))[0].model_dump(mode="json")
    await store_response(
        db, current_user.id, _PAYMENT_IDEMPOTENCY_ENDPOINT, idempotency_key, 201, body
    )
    return body


@router.get("/{customer_id}/payments", response_model=list[PaymentOut])
async def list_payments(
    customer_id: UUID,
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    await customer_service.get_or_404(db, customer_id)
    rows = await payment_service.list_customer_payments(db, customer_id, branch_id)
    return await payment_service.payments_out(db, rows)


@router.post("/{customer_id}/opening-balances", response_model=OpeningBalanceOut, status_code=201)
async def enter_opening_balance(
    customer_id: UUID,
    data: OpeningBalanceCreate,
    current_user=Depends(require_old_debt_enterer),
    db: AsyncSession = Depends(get_db),
):
    ob = await opening_balance_service.create(db, customer_id, data, current_user)
    return opening_balance_service.to_out(ob)


@router.get("/{customer_id}/statement", response_model=StatementOut)
async def customer_statement(
    customer_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: UUID | None = Depends(branch_context),  # a cashier gets their branch
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    today = business_date_today()
    return await statement_service.statement(
        db, customer_id, branch_id,
        date_from or today.replace(day=1), date_to or today,
    )
