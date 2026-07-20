from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse, ProductWithInventory,
    CategoryCreate, CategoryUpdate, CategoryResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.product_service import product_service

router = APIRouter(prefix="/products", tags=["Bidhaa"])

_admin = Depends(require_role("super_admin", "admin"))
_su = Depends(require_role("super_admin"))


def _prod_resp(p) -> ProductResponse:
    return ProductResponse(
        id=p.id, product_code=p.product_code, name=p.name,
        category=p.category.name, category_id=p.category_id,
        brand=p.brand, family_name=p.family_name,
        unit=p.unit or "Kipande", description=p.description,
        cost_price=p.cost_price, selling_price=p.selling_price,
        minimum_stock=p.minimum_stock, status=p.status,
        created_at=p.created_at,
    )


# ─── Categories (must be before /{product_id} to avoid UUID routing conflict) ─

@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await product_service.list_categories(db)


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    return await product_service.create_category(db, data, current_user)


@router.put("/categories/{cat_id}", response_model=CategoryResponse)
async def update_category(
    cat_id: int, data: CategoryUpdate,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    return await product_service.update_category(db, cat_id, data, current_user)


@router.delete("/categories/{cat_id}", response_model=MessageResponse)
async def delete_category(
    cat_id: int,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    await product_service.delete_category(db, cat_id, current_user)
    return {"message": "Jamii imefutwa"}


# ─── Products ─────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    search: str | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    status: str = "active",
    page: int = 1, per_page: int = 20,
    branch_id: UUID | None = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await product_service.list_products(
        db, search, category_id, brand, status, page, per_page, branch_id, current_user
    )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    product = await product_service.create_product(db, data, current_user)
    return _prod_resp(product)


@router.get("/{product_id}", response_model=ProductWithInventory)
async def get_product(
    product_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await product_service.get_with_inventory(db, product_id, current_user)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID, data: ProductUpdate,
    current_user=Depends(require_role("super_admin", "admin", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    product = await product_service.update_product(db, product_id, data, current_user)
    return _prod_resp(product)


@router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product(
    product_id: UUID,
    current_user=Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await product_service.soft_delete(db, product_id, current_user)
    return {"message": "Bidhaa imefutwa"}
