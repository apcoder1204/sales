"""Two cashiers at two branches sell on credit to the same customer at the
same moment: the customer row lock must stop them jointly exceeding the
one all-branch credit limit (spec §9, decision D4)."""
import asyncio
from decimal import Decimal

from app.core.exceptions import DebtException
from app.models.user import User
from app.schemas.sale import SaleCreate
from app.services import ledger_service
from app.services.sale_service import sale_service
from tests.debt_concurrency import World


async def test_concurrent_credit_sales_cannot_exceed_limit():
    w = World()
    try:
        s = w.session()
        a = await w.branch(s)
        b = await w.branch(s)
        cashier_a = await w.user(s, "cashier", a)
        cashier_b = await w.user(s, "cashier", b)
        product = await w.product(s, Decimal("400000"), Decimal("250000"))
        await w.inventory(s, product, a, 5)
        await w.inventory(s, product, b, 5)
        customer = await w.customer(s, Decimal("500000"))
        await s.commit()
        await s.close()

        async def attempt(branch, cashier):
            session = w.session()
            try:
                user = await session.get(User, cashier.id)
                data = SaleCreate(
                    branch_id=branch.id, customer_id=customer.id, payments=[],
                    items=[{"product_id": product.id, "quantity": 1}],
                )
                await sale_service.create_sale(session, data, user)
                return "ok"
            except DebtException as e:
                return e.code
            finally:
                await session.close()

        results = await asyncio.gather(attempt(a, cashier_a), attempt(b, cashier_b))
        assert sorted(results) == ["CREDIT_LIMIT_EXCEEDED", "ok"]

        verify = w.session()
        assert await ledger_service.customer_balance(verify, customer.id) == Decimal("400000")
        await verify.close()
    finally:
        await w.cleanup()
