import math
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_admin, require_cashier_access, require_role
from app.db.session import get_db
from app.schemas.customer import (
    CustomerCreate, CustomerCreditUpdate, CustomerDetailResponse, CustomerResponse, CustomerUpdate,
)
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])

# Everyone but store_keeper may look customers up (spec §6.5).
require_customer_reader = require_role("super_admin", "admin", "general_manager", "cashier")


@router.get("")
async def list_customers(
    q: str | None = Query(None, max_length=100),
    status: Literal["active", "inactive"] | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await customer_service.search(db, q, status, page, per_page)
    items = [CustomerResponse.model_validate(c) for c in rows]
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
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    return await customer_service.get_detail(db, customer_id, current_user)


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
