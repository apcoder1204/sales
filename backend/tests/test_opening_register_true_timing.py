"""Real-timestamp test for register period scoping — see
test_transfer_true_concurrency.py for why this can't use the rolled-back
savepoint fixtures: Postgres's `now()` (Sale.created_at's server default)
returns the *transaction start time*, frozen for the whole test, under the
savepoint-per-test isolation the rest of this suite uses. Proving that a
sale's timestamp correctly falls after a register's real opened_at (and
before/after a close) needs genuine separate committed transactions, each
with its own real `now()`, the way separate HTTP requests would have in
production. Commits real fixture rows, exercises the real open->sell->close
->open->sell->close sequence with real time gaps, then deletes everything
it created."""
import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from tests.conftest import UTC_CONNECT_ARGS
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.category import Category
from app.models.daily_closing import DailyClosing
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.role import Role
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.user import User
from app.schemas.daily_closing import CloseDayRequest, OpenRegisterRequest
from app.schemas.sale import SaleCreate, SaleItemInput
from app.services.daily_closing_service import daily_closing_service
from app.services.sale_service import sale_service


async def test_sales_after_closing_belong_to_a_new_register_period():
    engine = create_async_engine(settings.DATABASE_URL, connect_args=UTC_CONNECT_ARGS)
    setup = AsyncSession(bind=engine, expire_on_commit=False)
    ids = {}
    try:
        suffix = uuid.uuid4().hex[:8]
        branch = Branch(name=f"conc_reg_{suffix}", code=f"CR{suffix}", branch_type="pos_point")
        setup.add(branch)
        await setup.flush()
        ids["branch_id"] = branch.id

        admin_role = (await setup.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        cashier_role = (await setup.execute(select(Role).where(Role.name == "cashier"))).scalar_one()
        admin = User(
            username=f"conc_reg_admin_{suffix}", full_name="Register Admin",
            email=f"conc_reg_admin_{suffix}@test.local", password_hash=hash_password("Test1234"),
            role_id=admin_role.id, is_active=True,
        )
        cashier = User(
            username=f"conc_reg_cashier_{suffix}", full_name="Register Cashier",
            email=f"conc_reg_cashier_{suffix}@test.local", password_hash=hash_password("Test1234"),
            role_id=cashier_role.id, branch_id=branch.id, is_active=True,
        )
        setup.add_all([admin, cashier])
        await setup.flush()
        ids["admin_id"] = admin.id
        ids["cashier_id"] = cashier.id

        category = (await setup.execute(select(Category))).scalars().first()
        product = Product(
            product_code=f"CONCR-{suffix}", name=f"Register Test Product {suffix}",
            category_id=category.id, cost_price=100, selling_price=200, minimum_stock=1,
        )
        setup.add(product)
        await setup.flush()
        ids["product_id"] = product.id

        inv = Inventory(product_id=product.id, branch_id=branch.id, quantity=100, reserved_qty=0)
        setup.add(inv)
        await setup.flush()
        ids["inventory_id"] = inv.id
        await setup.commit()

        async def fresh_session():
            s = AsyncSession(bind=engine, expire_on_commit=False)
            return s, await s.get(User, admin.id), await s.get(User, cashier.id)

        # --- Register #1: open, one sale, close ---
        s1, admin1, cashier1 = await fresh_session()
        reg1 = await daily_closing_service.open_register(
            s1, OpenRegisterRequest(branch_id=branch.id, opening_cash=Decimal("10000")), admin1
        )
        reg1_id = reg1.id
        await s1.close()

        await asyncio.sleep(1.1)  # guarantee a real, distinguishable now() tick

        s2, admin2, cashier2 = await fresh_session()
        await sale_service.create_sale(
            s2,
            SaleCreate(
                branch_id=branch.id, payment_method="cash",
                items=[SaleItemInput(product_id=product.id, quantity=2)],
            ),
            cashier2,
        )
        await s2.close()

        await asyncio.sleep(1.1)

        s3, admin3, cashier3 = await fresh_session()
        close1 = await daily_closing_service.close_day(
            s3, CloseDayRequest(branch_id=branch.id, counted_cash=Decimal("0"), expenses=[]), admin3
        )
        close1_sales_count = close1.total_sales_count
        close1_revenue = close1.total_revenue
        await s3.close()

        await asyncio.sleep(1.1)

        # --- Register #2: open, one sale, close ---
        s4, admin4, cashier4 = await fresh_session()
        reg2 = await daily_closing_service.open_register(
            s4, OpenRegisterRequest(branch_id=branch.id, opening_cash=Decimal("5000")), admin4
        )
        reg2_id = reg2.id
        reg2_number = reg2.register_number
        await s4.close()

        await asyncio.sleep(1.1)

        s5, admin5, cashier5 = await fresh_session()
        await sale_service.create_sale(
            s5,
            SaleCreate(
                branch_id=branch.id, payment_method="cash",
                items=[SaleItemInput(product_id=product.id, quantity=1)],
            ),
            cashier5,
        )
        await s5.close()

        await asyncio.sleep(1.1)

        s6, admin6, cashier6 = await fresh_session()
        close2 = await daily_closing_service.close_day(
            s6, CloseDayRequest(branch_id=branch.id, counted_cash=Decimal("0"), expenses=[]), admin6
        )
        close2_sales_count = close2.total_sales_count
        close2_revenue = close2.total_revenue
        await s6.close()

        # Register #1 sold 2 units (400), register #2 sold 1 unit (200) —
        # each register's close must reflect ONLY its own period's sale,
        # never the other's.
        assert close1_sales_count == 1
        assert close1_revenue == Decimal("400.00")
        assert reg2_number == 2
        assert close2_sales_count == 1
        assert close2_revenue == Decimal("200.00")

        # Re-fetching register #1's own row afterward must show it
        # completely unchanged by register #2's close.
        verify = AsyncSession(bind=engine, expire_on_commit=False)
        reg1_after = await verify.get(DailyClosing, reg1_id)
        assert reg1_after.total_sales_count == 1
        assert reg1_after.total_revenue == Decimal("400.00")
        await verify.close()
    finally:
        cleanup = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            if "branch_id" in ids:
                sale_ids = (
                    await cleanup.execute(select(Sale.id).where(Sale.branch_id == ids["branch_id"]))
                ).scalars().all()
                if sale_ids:
                    await cleanup.execute(
                        delete(InventoryTransaction).where(InventoryTransaction.reference_id.in_(sale_ids))
                    )
                    await cleanup.execute(delete(SaleItem).where(SaleItem.sale_id.in_(sale_ids)))
                    await cleanup.execute(delete(Sale).where(Sale.id.in_(sale_ids)))
                await cleanup.execute(delete(DailyClosing).where(DailyClosing.branch_id == ids["branch_id"]))
                await cleanup.execute(delete(AuditLog).where(AuditLog.branch_id == ids["branch_id"]))
            if "inventory_id" in ids:
                await cleanup.execute(delete(Inventory).where(Inventory.id == ids["inventory_id"]))
            if "product_id" in ids:
                await cleanup.execute(delete(Product).where(Product.id == ids["product_id"]))
            for key in ("admin_id", "cashier_id"):
                if key in ids:
                    await cleanup.execute(delete(AuditLog).where(AuditLog.user_id == ids[key]))
                    await cleanup.execute(delete(User).where(User.id == ids[key]))
            if "branch_id" in ids:
                await cleanup.execute(delete(Branch).where(Branch.id == ids["branch_id"]))
            await cleanup.commit()
        finally:
            await cleanup.close()
            await setup.close()
            await engine.dispose()
