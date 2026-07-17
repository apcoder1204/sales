from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.inventory_repo import inventory_repo
from app.repositories.product_repo import product_repo
from app.schemas.inventory import AvailableSourcesResponse, SourceBranch
from app.core.exceptions import InsufficientStockException, NotFoundException
from app.services.audit_service import audit_service
import math


class InventoryService:
    async def adjust_stock(
        self, db: AsyncSession,
        product_id: UUID, branch_id: UUID,
        quantity: int, adj_type: str,
        notes: str | None, user
    ):
        product = await product_repo.get_by_id(db, product_id)
        if not product:
            raise NotFoundException("Bidhaa")

        async with db.begin_nested():
            inv = await inventory_repo.get_by_product_branch_locked(db, product_id, branch_id)
            if not inv:
                inv = await inventory_repo.create(db, {
                    "product_id": product_id,
                    "branch_id": branch_id,
                    "quantity": 0,
                    "reserved_qty": 0,
                })

            qty_before = inv.quantity
            multiplier = -1 if adj_type in ("stock_out", "damaged") else 1
            qty_change = quantity * multiplier
            qty_after = qty_before + qty_change

            if qty_after < 0:
                raise InsufficientStockException(product.name, qty_before, quantity)

            await inventory_repo.create_transaction(db, {
                "product_id": product_id,
                "branch_id": branch_id,
                "transaction_type": adj_type,
                "quantity_before": qty_before,
                "quantity_change": qty_change,
                "quantity_after": qty_after,
                "notes": notes,
                "performed_by": user.id,
            })
            await inventory_repo.update(db, inv.id, {"quantity": qty_after})

        await db.commit()
        await audit_service.log(
            db, action=adj_type.upper(), category="inventory",
            user_id=user.id, username=user.username, user_role=user.role.name,
            branch_id=branch_id, entity_type="inventory", entity_id=str(inv.id),
            details={
                "product": product.name, "qty_before": qty_before,
                "qty_change": qty_change, "qty_after": qty_after, "notes": notes
            }
        )
        return inv

    async def get_available_sources(
        self, db: AsyncSession,
        product_id: UUID, requested_qty: int, destination_branch_id: UUID
    ) -> AvailableSourcesResponse:
        main_branch = await inventory_repo.get_main_store(db)
        if not main_branch:
            return AvailableSourcesResponse(
                main_store_sufficient=False, main_store_stock=0, sources=[]
            )

        main_inv = await inventory_repo.get_by_product_branch(db, product_id, main_branch.id)
        main_avail = (main_inv.quantity - main_inv.reserved_qty) if main_inv else 0

        if main_avail >= requested_qty:
            return AvailableSourcesResponse(
                main_store_sufficient=True,
                main_store_stock=main_avail,
                sources=[]
            )

        alt_sources = await inventory_repo.get_available_sources(
            db, product_id, requested_qty, exclude_branch_id=destination_branch_id
        )
        return AvailableSourcesResponse(
            main_store_sufficient=False,
            main_store_stock=main_avail,
            sources=[SourceBranch(**s) for s in alt_sources]
        )

    async def get_inventory_list(
        self, db: AsyncSession, branch_id: UUID | None,
        low_stock: bool, page: int, per_page: int
    ):
        from sqlalchemy import select
        from app.models.inventory import Inventory
        from app.models.product import Product
        from app.models.branch import Branch
        from app.schemas.product import ProductWithInventory, BranchStock, ProductResponse
        skip = (page - 1) * per_page

        q = (
            select(Product)
            .where(Product.status == "active")
            .order_by(Product.name)
        )
        from sqlalchemy import func
        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        products = (await db.execute(q.offset(skip).limit(per_page))).scalars().all()

        result = []
        for p in products:
            inv_q = select(Inventory, Branch).join(Branch, Inventory.branch_id == Branch.id).where(
                Inventory.product_id == p.id, Branch.is_active == True
            )
            if branch_id:
                inv_q = inv_q.where(Inventory.branch_id == branch_id)
            inv_rows = (await db.execute(inv_q)).all()

            if low_stock and not any(i.quantity <= p.minimum_stock for i, _ in inv_rows):
                continue

            stocks = [
                BranchStock(
                    branch_id=b.id, branch_name=b.name, branch_code=b.code,
                    branch_type=b.branch_type,
                    quantity=i.quantity, reserved_qty=i.reserved_qty,
                    available_qty=i.quantity - i.reserved_qty,
                    is_low_stock=i.quantity <= p.minimum_stock,
                ) for i, b in inv_rows
            ]
            result.append(ProductWithInventory(
                id=p.id, product_code=p.product_code, name=p.name,
                category=p.category.name, category_id=p.category_id,
                brand=p.brand, family_name=p.family_name,
                cost_price=p.cost_price, selling_price=p.selling_price,
                minimum_stock=p.minimum_stock, status=p.status,
                created_at=p.created_at, inventory=stocks,
            ))

        return {"items": result, "total": total, "page": page, "per_page": per_page,
                "pages": math.ceil(total / per_page) if total else 1}


inventory_service = InventoryService()
