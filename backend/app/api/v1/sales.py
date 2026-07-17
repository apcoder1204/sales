from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.schemas.sale import SaleCreate, SaleResponse, SaleCreateResponse, SaleVoidRequest
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.sale_service import sale_service
from app.repositories.sale_repo import sale_repo
from app.core.exceptions import InsufficientPermissionException
import math

router = APIRouter(prefix="/sales", tags=["Mauzo"])


@router.post("", response_model=SaleCreateResponse, status_code=201)
async def create_sale(
    data: SaleCreate,
    current_user=Depends(require_role("super_admin", "admin", "cashier")),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name == "cashier":
        if str(current_user.branch_id) != str(data.branch_id):
            raise InsufficientPermissionException("Huwezi kuuza kutoka tawi lingine")
    sale, receipt = await sale_service.create_sale(db, data, current_user)
    return SaleCreateResponse(
        sale=SaleResponse(
            id=sale.id, transaction_no=sale.transaction_no,
            branch=sale.branch.name, branch_id=sale.branch_id,
            cashier=sale.cashier.full_name, cashier_id=sale.cashier_id,
            subtotal=sale.subtotal, total_amount=sale.total_amount,
            payment_method=sale.payment_method,
            payment_reference=sale.payment_reference,
            status=sale.status,
            items=[
                __import__("app.schemas.sale", fromlist=["SaleItemResponse"]).SaleItemResponse(
                    id=i.id, product_id=i.product_id, product=i.product.name,
                    quantity=i.quantity, unit_price=i.unit_price,
                    cost_price=i.cost_price, line_total=i.line_total,
                ) for i in sale.items
            ],
            created_at=sale.created_at,
        ),
        receipt=receipt,
    )


@router.get("")
async def list_sales(
    branch_id: UUID | None = None,
    cashier_id: UUID | None = None,
    payment_method: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1, per_page: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role.name == "cashier":
        cashier_id = current_user.id
        branch_id = current_user.branch_id
    skip = (page - 1) * per_page
    rows, total = await sale_repo.list_sales(
        db, branch_id, cashier_id, payment_method, from_date, to_date, skip, per_page
    )
    items = [
        SaleResponse(
            id=s.id, transaction_no=s.transaction_no,
            branch=s.branch.name, branch_id=s.branch_id,
            cashier=s.cashier.full_name, cashier_id=s.cashier_id,
            subtotal=s.subtotal, total_amount=s.total_amount,
            payment_method=s.payment_method, payment_reference=s.payment_reference,
            status=s.status,
            items=[
                __import__("app.schemas.sale", fromlist=["SaleItemResponse"]).SaleItemResponse(
                    id=i.id, product_id=i.product_id, product=i.product.name,
                    quantity=i.quantity, unit_price=i.unit_price,
                    cost_price=i.cost_price, line_total=i.line_total,
                ) for i in s.items
            ],
            created_at=s.created_at,
        ) for s in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": math.ceil(total / per_page) if total else 1}


@router.post("/{sale_id}/void", response_model=MessageResponse)
async def void_sale(
    sale_id: UUID, data: SaleVoidRequest,
    current_user=Depends(require_role("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await sale_service.void_sale(db, sale_id, data.reason, current_user)
    return {"message": "Muamala umebatilishwa"}
