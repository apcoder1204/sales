from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.product_repo import product_repo
from app.repositories.inventory_repo import inventory_repo
from app.schemas.product import ProductCreate, ProductUpdate, ProductWithInventory, BranchStock
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundException, DuplicateException
from app.services.audit_service import audit_service
import math


class ProductService:
    async def list_products(
        self, db: AsyncSession,
        search: str | None, category_id: int | None,
        brand: str | None, status: str,
        page: int, per_page: int,
        branch_id: UUID | None = None,
    ):
        skip = (page - 1) * per_page
        products, total, stock_by_product = await product_repo.list_products(
            db, search, category_id, brand, status, skip, per_page, branch_id
        )
        from app.schemas.product import ProductResponse
        items = []
        for p in products:
            available_qty = None
            is_low_stock = None
            if branch_id:
                inv = stock_by_product.get(p.id)
                available_qty = (inv.quantity - inv.reserved_qty) if inv else 0
                is_low_stock = available_qty <= p.minimum_stock
            items.append(ProductResponse(
                id=p.id, product_code=p.product_code, name=p.name,
                category=p.category.name, category_id=p.category_id,
                brand=p.brand, family_name=p.family_name,
                unit=p.unit or "Kipande", description=p.description,
                cost_price=p.cost_price, selling_price=p.selling_price,
                minimum_stock=p.minimum_stock, status=p.status,
                created_at=p.created_at,
                available_qty=available_qty, is_low_stock=is_low_stock,
            ))
        return PaginatedResponse(
            items=items, total=total, page=page,
            per_page=per_page, pages=math.ceil(total / per_page) if total else 1
        )

    async def get_with_inventory(self, db: AsyncSession, product_id: UUID, user) -> ProductWithInventory:
        from sqlalchemy import select
        from app.models.inventory import Inventory
        from app.models.branch import Branch
        product = await product_repo.get_by_id(db, product_id)
        if not product:
            raise NotFoundException("Bidhaa")

        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(Inventory, Branch)
            .join(Branch, Inventory.branch_id == Branch.id)
            .where(Inventory.product_id == product_id, Branch.is_active == True)
        )
        inventory_rows = result.all()
        branch_stocks = [
            BranchStock(
                branch_id=branch.id,
                branch_name=branch.name,
                branch_code=branch.code,
                branch_type=branch.branch_type,
                quantity=inv.quantity,
                reserved_qty=inv.reserved_qty,
                available_qty=inv.quantity - inv.reserved_qty,
                is_low_stock=inv.quantity <= product.minimum_stock,
            )
            for inv, branch in inventory_rows
        ]
        return ProductWithInventory(
            id=product.id, product_code=product.product_code, name=product.name,
            category=product.category.name, category_id=product.category_id,
            brand=product.brand, family_name=product.family_name,
            unit=product.unit or "Kipande", description=product.description,
            cost_price=product.cost_price, selling_price=product.selling_price,
            minimum_stock=product.minimum_stock, status=product.status,
            created_at=product.created_at, inventory=branch_stocks,
        )

    async def create_product(self, db: AsyncSession, data: ProductCreate, user) -> dict:
        code = data.product_code if data.product_code else await product_repo.get_next_code(db)
        product = await product_repo.create(db, {
            "product_code": code,
            "name": data.name,
            "category_id": data.category_id,
            "brand": data.brand,
            "family_name": data.family_name,
            "family_id": data.family_id,
            "unit": data.unit,
            "description": data.description,
            "cost_price": data.cost_price,
            "selling_price": data.selling_price,
            "minimum_stock": data.minimum_stock,
            "created_by": user.id,
        })
        await db.commit()
        await audit_service.log(
            db, action="PRODUCT_CREATED", category="products",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="product", entity_id=str(product.id),
            details={"name": product.name, "code": product.product_code}
        )
        return product

    async def update_product(self, db: AsyncSession, product_id: UUID, data: ProductUpdate, user):
        product = await product_repo.get_by_id(db, product_id)
        if not product:
            raise NotFoundException("Bidhaa")
        before = {"name": product.name, "selling_price": str(product.selling_price)}
        updates = data.model_dump(exclude_none=True)
        product = await product_repo.update(db, product_id, updates)
        await db.commit()
        await audit_service.log(
            db, action="PRODUCT_UPDATED", category="products",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="product", entity_id=str(product_id),
            details={"before": before, "after": updates}
        )
        return product

    async def soft_delete(self, db: AsyncSession, product_id: UUID, user):
        product = await product_repo.get_by_id(db, product_id)
        if not product:
            raise NotFoundException("Bidhaa")
        await product_repo.update(db, product_id, {"status": "inactive"})
        await db.commit()
        await audit_service.log(
            db, action="PRODUCT_DELETED", category="products",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="product", entity_id=str(product_id),
            details={"name": product.name}
        )

    async def list_categories(self, db: AsyncSession):
        return await product_repo.list_categories(db)

    async def create_category(self, db: AsyncSession, data, user):
        from app.models.category import Category
        from sqlalchemy import select
        if data.category_code:
            exists_code = (await db.execute(select(Category).where(Category.category_code == data.category_code))).scalar_one_or_none()
            if exists_code:
                raise DuplicateException("Msimbo wa Jamii")
        cat = Category(
            name=data.name,
            name_sw=data.name_sw,
            category_code=data.category_code,
            brand_name=data.brand_name,
            family=data.family,
            description=data.description,
        )
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        await audit_service.log(
            db, action="CATEGORY_CREATED", category="products",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="category", entity_id=str(cat.id),
            details={"name": cat.name, "code": cat.category_code}
        )
        return cat

    async def update_category(self, db: AsyncSession, cat_id: int, data, user):
        from app.models.category import Category
        cat = (await db.get(Category, cat_id))
        if not cat:
            raise NotFoundException("Jamii")
        before = {"name": cat.name}
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(cat, field, value)
        await db.commit()
        await db.refresh(cat)
        await audit_service.log(
            db, action="CATEGORY_UPDATED", category="products",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="category", entity_id=str(cat.id),
            details={"before": before, "after": data.model_dump(exclude_none=True)}
        )
        return cat

    async def delete_category(self, db: AsyncSession, cat_id: int, user):
        from app.models.category import Category
        from app.models.product import Product
        from sqlalchemy import select
        cat = await db.get(Category, cat_id)
        if not cat:
            raise NotFoundException("Jamii")
        used = (await db.execute(select(Product.id).where(Product.category_id == cat_id).limit(1))).scalar_one_or_none()
        if used:
            raise DuplicateException("Jamii inatumika na bidhaa, haiwezi kufutwa")
        await db.delete(cat)
        await db.commit()
        await audit_service.log(
            db, action="CATEGORY_DELETED", category="products",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="category", entity_id=str(cat_id),
            details={"name": cat.name}
        )


product_service = ProductService()
