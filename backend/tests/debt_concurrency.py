"""Committed-fixture helpers for the customer-debt true-concurrency tests.

These tests race independent connections, so they cannot use the rolled-back
savepoint fixtures (see test_sale_void_true_concurrency.py). `World` commits
real rows and `World.cleanup()` removes everything they produced — including
append-only ledger rows, via `SET LOCAL dukani.ledger_maintenance = 'on'`.
"""
import uuid
from decimal import Decimal

from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.category import Category
from app.models.customer import Customer
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.daily_closing import DailyClosing
from app.models.idempotency_key import IdempotencyKey
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment, PaymentAllocation
from app.models.product import Product
from app.models.reconciliation import ReconciliationException, ReconciliationRun
from app.models.role import Role
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.user import User
from tests.conftest import UTC_CONNECT_ARGS


class World:
    def __init__(self):
        self.engine = create_async_engine(settings.DATABASE_URL, connect_args=UTC_CONNECT_ARGS)
        self.suffix = uuid.uuid4().hex[:8]
        self.branch_ids: list = []
        self.user_ids: list = []
        self.product_ids: list = []
        self.customer_ids: list = []

    def session(self) -> AsyncSession:
        return AsyncSession(bind=self.engine, expire_on_commit=False)

    async def branch(self, s: AsyncSession) -> Branch:
        n = len(self.branch_ids)
        b = Branch(name=f"debt_conc_{self.suffix}_{n}", code=f"DC{self.suffix}{n}", branch_type="pos_point")
        s.add(b)
        await s.flush()
        self.branch_ids.append(b.id)
        return b

    async def user(self, s: AsyncSession, role: str, branch: Branch | None = None) -> User:
        role_row = (await s.execute(select(Role).where(Role.name == role))).scalar_one()
        n = len(self.user_ids)
        u = User(
            username=f"dc_{role[:4]}_{self.suffix}_{n}", full_name=f"Debt Conc {role} {n}",
            email=f"dc_{self.suffix}_{n}@test.local", password_hash=hash_password("Test1234"),
            role_id=role_row.id, branch_id=branch.id if branch else None, is_active=True,
        )
        s.add(u)
        await s.flush()
        self.user_ids.append(u.id)
        return u

    async def product(self, s: AsyncSession, price: Decimal, cost: Decimal) -> Product:
        category = (await s.execute(select(Category))).scalars().first()
        p = Product(
            product_code=f"DC-{self.suffix}-{len(self.product_ids)}",
            name=f"Debt Conc Product {self.suffix}", category_id=category.id,
            cost_price=cost, selling_price=price, minimum_stock=1,
        )
        s.add(p)
        await s.flush()
        self.product_ids.append(p.id)
        return p

    async def inventory(self, s: AsyncSession, product: Product, branch: Branch, qty: int):
        s.add(Inventory(product_id=product.id, branch_id=branch.id, quantity=qty, reserved_qty=0))
        await s.flush()

    async def customer(self, s: AsyncSession, credit_limit: Decimal) -> Customer:
        seq = (await s.execute(text("SELECT nextval('seq_customer_number')"))).scalar()
        c = Customer(
            customer_no=f"CUS-{seq:04d}", name=f"Debt Conc Customer {self.suffix}",
            phone=f"2556{uuid.uuid4().int % 100_000_000:08d}", credit_limit=credit_limit,
        )
        s.add(c)
        await s.flush()
        self.customer_ids.append(c.id)
        return c

    async def cleanup(self):
        s = self.session()
        try:
            await s.execute(text("SET LOCAL dukani.ledger_maintenance = 'on'"))
            sale_ids = select(Sale.id).where(Sale.branch_id.in_(self.branch_ids))
            payment_ids = select(Payment.id).where(Payment.branch_id.in_(self.branch_ids))
            runs = select(ReconciliationRun.id).where(ReconciliationRun.run_by.in_(self.user_ids))
            await s.execute(delete(ReconciliationException).where(or_(
                ReconciliationException.branch_id.in_(self.branch_ids),
                ReconciliationException.customer_id.in_(self.customer_ids),
                ReconciliationException.first_run_id.in_(runs), ReconciliationException.last_run_id.in_(runs),
            )))
            await s.execute(delete(ReconciliationRun).where(ReconciliationRun.run_by.in_(self.user_ids)))
            await s.execute(delete(AuditLog).where(or_(
                AuditLog.branch_id.in_(self.branch_ids), AuditLog.user_id.in_(self.user_ids),
            )))
            await s.execute(delete(IdempotencyKey).where(IdempotencyKey.user_id.in_(self.user_ids)))
            await s.execute(delete(CustomerLedgerEntry).where(
                CustomerLedgerEntry.customer_id.in_(self.customer_ids)
            ))
            await s.execute(delete(PaymentAllocation).where(or_(
                PaymentAllocation.payment_id.in_(payment_ids), PaymentAllocation.sale_id.in_(sale_ids),
            )))
            await s.execute(delete(Payment).where(Payment.branch_id.in_(self.branch_ids)))
            await s.execute(delete(OpeningBalance).where(OpeningBalance.customer_id.in_(self.customer_ids)))
            await s.execute(delete(SaleItem).where(SaleItem.sale_id.in_(sale_ids)))
            await s.execute(delete(InventoryTransaction).where(
                InventoryTransaction.branch_id.in_(self.branch_ids)
            ))
            await s.execute(delete(Sale).where(Sale.branch_id.in_(self.branch_ids)))
            await s.execute(delete(Inventory).where(Inventory.branch_id.in_(self.branch_ids)))
            await s.execute(delete(DailyClosing).where(DailyClosing.branch_id.in_(self.branch_ids)))
            await s.execute(delete(Customer).where(Customer.id.in_(self.customer_ids)))
            await s.execute(delete(Product).where(Product.id.in_(self.product_ids)))
            await s.execute(delete(User).where(User.id.in_(self.user_ids)))
            await s.execute(delete(Branch).where(Branch.id.in_(self.branch_ids)))
            await s.commit()
        finally:
            await s.close()
            await self.engine.dispose()
