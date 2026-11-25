"""Racing debt payments / reversals on separate committed connections
(spec §9): the customer lock stops two payments overpaying one debt, and
the payment row lock stops a double reversal."""
import asyncio
from decimal import Decimal

from sqlalchemy import func, select

from app.core.exceptions import DebtException
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.user import User
from app.schemas.payment import DebtPaymentCreate
from app.schemas.sale import SaleCreate
from app.services import payment_service
from app.services.sale_service import sale_service
from tests.debt_concurrency import World


async def _debt_world(w: World, price: Decimal):
    s = w.session()
    branch = await w.branch(s)
    cashier = await w.user(s, "cashier", branch)
    admin = await w.user(s, "admin")
    product = await w.product(s, price, Decimal("1000"))
    await w.inventory(s, product, branch, 5)
    customer = await w.customer(s, Decimal("5000000"))
    await s.commit()
    await s.close()
    s = w.session()
    sale, _ = await sale_service.create_sale(s, SaleCreate(
        branch_id=branch.id, customer_id=customer.id, payments=[],
        items=[{"product_id": product.id, "quantity": 1}],
    ), await s.get(User, cashier.id))
    await s.close()
    return branch, cashier, admin, customer, sale


async def test_concurrent_payments_cannot_overpay():
    w = World()
    try:
        branch, cashier, _, customer, sale = await _debt_world(w, Decimal("300000"))

        async def attempt():
            session = w.session()
            try:
                user = await session.get(User, cashier.id)
                await payment_service.record_debt_payment(
                    session, customer.id,
                    DebtPaymentCreate(method="cash", amount=Decimal("200000")), user,
                )
                return "ok"
            except DebtException as e:
                return e.code
            finally:
                await session.close()

        results = await asyncio.gather(attempt(), attempt())
        assert sorted(results) == ["PAYMENT_EXCEEDS_DEBT", "ok"]

        v = w.session()
        applied = (await v.execute(
            select(func.sum(PaymentAllocation.amount))
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(PaymentAllocation.sale_id == sale.id, Payment.status == "active")
        )).scalar()
        assert applied == Decimal("200000")
        await v.close()
    finally:
        await w.cleanup()


async def test_concurrent_reversals():
    w = World()
    try:
        branch, cashier, admin, customer, sale = await _debt_world(w, Decimal("300000"))
        s = w.session()
        payment = await payment_service.record_debt_payment(
            s, customer.id, DebtPaymentCreate(method="cash", amount=Decimal("100000")),
            await s.get(User, cashier.id),
        )
        await s.close()

        async def attempt():
            session = w.session()
            try:
                user = await session.get(User, admin.id)
                await payment_service.reverse_payment(session, payment.id, "Imerekodiwa mara mbili", user)
                return "ok"
            except DebtException as e:
                return e.code
            finally:
                await session.close()

        results = await asyncio.gather(attempt(), attempt())
        assert sorted(results) == ["PAYMENT_ALREADY_REVERSED", "ok"]

        v = w.session()
        n = (await v.execute(select(func.count()).select_from(CustomerLedgerEntry).where(
            CustomerLedgerEntry.source_id == payment.id,
            CustomerLedgerEntry.entry_type == "payment_reversal",
        ))).scalar()
        assert n == 1
        await v.close()
    finally:
        await w.cleanup()
