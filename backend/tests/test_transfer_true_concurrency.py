"""Genuine cross-connection concurrency test for stock-request approval.

Unlike the rest of the suite, this test cannot use the rolled-back-savepoint
`db_session`/`client` fixtures: proving the SELECT ... FOR UPDATE lock in
TransferService.approve_request actually serializes two concurrent callers
requires two independent physical DB connections/transactions racing against
*committed* rows — a savepoint-isolated single connection can't reproduce
that. So this test commits its own fixture rows for real, runs the race, and
deletes everything it created (by exact ID, in FK-safe order) in a finally
block — nothing here is left behind in the shared dev database.
"""
import asyncio
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from tests.conftest import UTC_CONNECT_ARGS
from app.core.exceptions import ValidationException
from app.core.security import hash_password
from app.models.branch import Branch
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.role import Role
from app.models.stock_request import StockRequest
from app.models.stock_request_item import StockRequestItem
from app.models.user import User
from app.schemas.transfer import StockRequestApprovalRequest, StockRequestItemApproval
from app.services.transfer_service import transfer_service


async def test_concurrent_approval_cannot_over_reserve():
    engine = create_async_engine(settings.DATABASE_URL, connect_args=UTC_CONNECT_ARGS)
    setup = AsyncSession(bind=engine, expire_on_commit=False)
    ids = {}
    try:
        main_store = (
            await setup.execute(
                select(Branch).where(Branch.branch_type == "main_store", Branch.is_active == True)
            )
        ).scalars().first()
        assert main_store is not None, "seeded dev DB must have an active main store"

        suffix = uuid.uuid4().hex[:8]
        pos_branch = Branch(name=f"conc_pos_{suffix}", code=f"CP{suffix}", branch_type="pos_point")
        setup.add(pos_branch)
        await setup.flush()
        ids["branch_id"] = pos_branch.id

        admin_role = (await setup.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        admin = User(
            username=f"conc_admin_{suffix}",
            full_name="Concurrency Test Admin",
            email=f"conc_{suffix}@test.local",
            password_hash=hash_password("Test1234"),
            role_id=admin_role.id,
            is_active=True,
        )
        setup.add(admin)
        await setup.flush()
        ids["user_id"] = admin.id

        category = (await setup.execute(select(Category))).scalars().first()
        product = Product(
            product_code=f"CONC-{suffix}",
            name=f"Concurrency Product {suffix}",
            category_id=category.id,
            cost_price=100,
            selling_price=200,
            minimum_stock=1,
        )
        setup.add(product)
        await setup.flush()
        ids["product_id"] = product.id

        inv = Inventory(product_id=product.id, branch_id=main_store.id, quantity=5, reserved_qty=0)
        setup.add(inv)
        await setup.flush()
        ids["inventory_id"] = inv.id

        req = StockRequest(
            request_no=f"REQ-CONC-{suffix}",
            requested_by=admin.id,
            from_branch_id=main_store.id,
            to_branch_id=pos_branch.id,
            reason="concurrency test",
        )
        setup.add(req)
        await setup.flush()
        ids["request_id"] = req.id

        item = StockRequestItem(
            request_id=req.id, product_id=product.id, requested_qty=5, main_store_had_stock=True
        )
        setup.add(item)
        await setup.flush()
        ids["item_id"] = item.id

        await setup.commit()

        # Two independent sessions => two independent physical connections
        # and transactions, so their SELECT ... FOR UPDATE calls genuinely
        # contend on the same StockRequest row instead of sharing one
        # transaction's lock space.
        session_a = AsyncSession(bind=engine, expire_on_commit=False)
        session_b = AsyncSession(bind=engine, expire_on_commit=False)
        admin_a = await session_a.get(User, admin.id)
        admin_b = await session_b.get(User, admin.id)

        approval = StockRequestApprovalRequest(
            items=[StockRequestItemApproval(item_id=item.id, approved_qty=5)], notes="race"
        )

        async def attempt(session, user):
            try:
                await transfer_service.approve_request(session, req.id, approval, user)
                return "ok"
            except ValidationException:
                return "conflict"
            finally:
                await session.close()

        results = await asyncio.gather(
            attempt(session_a, admin_a), attempt(session_b, admin_b)
        )

        # Exactly one caller wins the race; the loser gets a clean business
        # conflict (ValidationException -> 400), never a raw DB error, and
        # never a second silent reservation.
        assert sorted(results) == ["conflict", "ok"]

        verify = AsyncSession(bind=engine, expire_on_commit=False)
        fresh_inv = await verify.get(Inventory, inv.id)
        assert fresh_inv.reserved_qty == 5, "stock must be reserved exactly once, not twice"
        await verify.close()
    finally:
        cleanup = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            from app.models.stock_transfer import StockTransfer
            from app.models.stock_transfer_item import StockTransferItem

            if "request_id" in ids:
                transfers = (
                    await cleanup.execute(
                        select(StockTransfer.id).where(StockTransfer.request_id == ids["request_id"])
                    )
                ).scalars().all()
                if transfers:
                    await cleanup.execute(
                        delete(StockTransferItem).where(StockTransferItem.transfer_id.in_(transfers))
                    )
                    await cleanup.execute(delete(StockTransfer).where(StockTransfer.id.in_(transfers)))
                await cleanup.execute(
                    delete(StockRequestItem).where(StockRequestItem.request_id == ids["request_id"])
                )
                await cleanup.execute(delete(StockRequest).where(StockRequest.id == ids["request_id"]))
            if "inventory_id" in ids:
                await cleanup.execute(delete(Inventory).where(Inventory.id == ids["inventory_id"]))
            if "product_id" in ids:
                await cleanup.execute(delete(Product).where(Product.id == ids["product_id"]))
            if "user_id" in ids:
                await cleanup.execute(delete(User).where(User.id == ids["user_id"]))
            if "branch_id" in ids:
                await cleanup.execute(delete(Branch).where(Branch.id == ids["branch_id"]))
            await cleanup.commit()
        finally:
            await cleanup.close()
            await setup.close()
            await engine.dispose()
