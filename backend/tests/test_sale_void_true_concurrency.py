"""Genuine cross-connection concurrency test for sale void — see
test_transfer_true_concurrency.py for why this can't use the rolled-back
savepoint fixtures. Commits real fixture rows, races two independent
connections, then deletes everything it created."""
import asyncio
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.core.exceptions import ValidationException
from app.core.security import hash_password
from app.models.branch import Branch
from app.models.category import Category
from app.models.audit_log import AuditLog
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.role import Role
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.user import User
from app.services.sale_service import sale_service


async def test_concurrent_void_cannot_restore_inventory_twice():
    engine = create_async_engine(settings.DATABASE_URL)
    setup = AsyncSession(bind=engine, expire_on_commit=False)
    ids = {}
    try:
        suffix = uuid.uuid4().hex[:8]
        branch = Branch(name=f"conc_sale_{suffix}", code=f"CS{suffix}", branch_type="pos_point")
        setup.add(branch)
        await setup.flush()
        ids["branch_id"] = branch.id

        cashier_role = (await setup.execute(select(Role).where(Role.name == "cashier"))).scalar_one()
        admin_role = (await setup.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        cashier = User(
            username=f"conc_cash_{suffix}", full_name="Concurrency Cashier",
            email=f"conc_cash_{suffix}@test.local", password_hash=hash_password("Test1234"),
            role_id=cashier_role.id, branch_id=branch.id, is_active=True,
        )
        admin = User(
            username=f"conc_adm_{suffix}", full_name="Concurrency Admin",
            email=f"conc_adm_{suffix}@test.local", password_hash=hash_password("Test1234"),
            role_id=admin_role.id, is_active=True,
        )
        setup.add_all([cashier, admin])
        await setup.flush()
        ids["cashier_id"] = cashier.id
        ids["admin_id"] = admin.id

        category = (await setup.execute(select(Category))).scalars().first()
        product = Product(
            product_code=f"CONCS-{suffix}", name=f"Concurrency Sale Product {suffix}",
            category_id=category.id, cost_price=100, selling_price=200, minimum_stock=1,
        )
        setup.add(product)
        await setup.flush()
        ids["product_id"] = product.id

        inv = Inventory(product_id=product.id, branch_id=branch.id, quantity=10, reserved_qty=0)
        setup.add(inv)
        await setup.flush()
        ids["inventory_id"] = inv.id

        sale = Sale(
            transaction_no=f"TXN-CONC-{suffix}", branch_id=branch.id, cashier_id=cashier.id,
            subtotal=600, total_amount=600, payment_method="cash", status="completed",
        )
        setup.add(sale)
        await setup.flush()
        ids["sale_id"] = sale.id

        sale_item = SaleItem(
            sale_id=sale.id, product_id=product.id, quantity=3,
            unit_price=200, cost_price=100, line_total=600,
        )
        setup.add(sale_item)
        await setup.flush()
        ids["sale_item_id"] = sale_item.id

        # Reflect the sale in inventory the same way create_sale would.
        inv.quantity = 7
        await setup.flush()
        await setup.commit()

        session_a = AsyncSession(bind=engine, expire_on_commit=False)
        session_b = AsyncSession(bind=engine, expire_on_commit=False)
        admin_a = await session_a.get(User, admin.id)
        admin_b = await session_b.get(User, admin.id)

        async def attempt(session, user):
            try:
                await sale_service.void_sale(session, sale.id, "concurrent void race", user)
                return "ok"
            except ValidationException:
                return "conflict"
            finally:
                await session.close()

        results = await asyncio.gather(attempt(session_a, admin_a), attempt(session_b, admin_b))
        assert sorted(results) == ["conflict", "ok"]

        verify = AsyncSession(bind=engine, expire_on_commit=False)
        fresh_inv = await verify.get(Inventory, inv.id)
        assert fresh_inv.quantity == 10, "stock must be restored exactly once, not twice"
        tx_count = (
            await verify.execute(
                select(InventoryTransaction).where(
                    InventoryTransaction.reference_id == sale.id,
                    InventoryTransaction.reference_type == "sale_void",
                )
            )
        ).scalars().all()
        assert len(tx_count) == 1, "exactly one reversal ledger entry, not two"
        await verify.close()
    finally:
        cleanup = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            if "sale_id" in ids:
                await cleanup.execute(delete(AuditLog).where(AuditLog.entity_id == str(ids["sale_id"])))
            if "branch_id" in ids:
                await cleanup.execute(delete(AuditLog).where(AuditLog.branch_id == ids["branch_id"]))
            if "sale_id" in ids:
                await cleanup.execute(
                    delete(InventoryTransaction).where(InventoryTransaction.reference_id == ids["sale_id"])
                )
                await cleanup.execute(delete(SaleItem).where(SaleItem.sale_id == ids["sale_id"]))
                await cleanup.execute(delete(Sale).where(Sale.id == ids["sale_id"]))
            if "inventory_id" in ids:
                await cleanup.execute(delete(Inventory).where(Inventory.id == ids["inventory_id"]))
            if "product_id" in ids:
                await cleanup.execute(delete(Product).where(Product.id == ids["product_id"]))
            if "cashier_id" in ids:
                await cleanup.execute(delete(User).where(User.id == ids["cashier_id"]))
            if "admin_id" in ids:
                await cleanup.execute(delete(User).where(User.id == ids["admin_id"]))
            if "branch_id" in ids:
                await cleanup.execute(delete(Branch).where(Branch.id == ids["branch_id"]))
            await cleanup.commit()
        finally:
            await cleanup.close()
            await setup.close()
            await engine.dispose()
