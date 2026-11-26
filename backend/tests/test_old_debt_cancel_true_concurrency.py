"""Cancelling an old debt while a cashier pays it, on separate committed
connections: the customer lock makes exactly one of them win, and the books
always agree with the outcome."""
import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.business_time import business_date_today
from app.core.exceptions import DebtException
from app.models.payment import Payment, PaymentAllocation
from app.models.user import User
from app.schemas.payment import DebtPaymentCreate, OpeningBalanceCreate
from app.services import ledger_service, opening_balance_service, payment_service
from tests.debt_concurrency import World


async def test_cancel_and_payment_race_has_one_winner():
    w = World()
    try:
        s = w.session()
        branch = await w.branch(s)
        cashier = await w.user(s, "cashier", branch)
        admin = await w.user(s, "admin")
        customer = await w.customer(s, Decimal("0"))
        await s.commit()
        await s.close()

        for i in range(3):
            s = w.session()
            ob = await opening_balance_service.create(s, customer.id, OpeningBalanceCreate(
                branch_id=branch.id, amount=Decimal("300000"), reference=f"Daftari uk. {i}",
                effective_date=business_date_today() - timedelta(days=10),
            ), await s.get(User, admin.id))
            await opening_balance_service.approve(s, ob.id, await s.get(User, admin.id), None)
            await s.close()

            async def cancel():
                session = w.session()
                try:
                    await opening_balance_service.cancel(
                        session, ob.id, await session.get(User, admin.id), "Kiasi si sahihi")
                    return "cancelled"
                except DebtException as e:
                    return e.code
                finally:
                    await session.close()

            async def pay():
                session = w.session()
                try:
                    await payment_service.record_debt_payment(
                        session, customer.id,
                        DebtPaymentCreate(method="cash", amount=Decimal("100000")),
                        await session.get(User, cashier.id),
                    )
                    return "paid"
                except DebtException as e:
                    return e.code
                finally:
                    await session.close()

            # return_exceptions: both tasks always finish before we assert or
            # clean up, even if one fails unexpectedly.
            outcomes = await asyncio.gather(cancel(), pay(), return_exceptions=True)
            results = {o if isinstance(o, str) else f"{type(o).__name__}: {o}" for o in outcomes}
            assert results in ({"cancelled", "PAYMENT_EXCEEDS_DEBT"}, {"paid", "OPENING_BALANCE_HAS_PAYMENTS"}), results

            s = w.session()
            balance = await ledger_service.customer_balance(s, customer.id)
            paid_on_it = (await s.execute(
                select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
                .join(Payment, Payment.id == PaymentAllocation.payment_id)
                .where(PaymentAllocation.opening_balance_id == ob.id, Payment.status == "active")
            )).scalar()
            if "cancelled" in results:
                assert paid_on_it == 0
            else:
                assert paid_on_it == Decimal("100000")
                # leave this debt fully settled so the next round starts clean
                await payment_service.record_debt_payment(
                    s, customer.id, DebtPaymentCreate(method="cash", amount=Decimal("200000")),
                    await s.get(User, cashier.id),
                )
                balance = await ledger_service.customer_balance(s, customer.id)
            assert balance == Decimal("0"), balance
            await s.close()
    finally:
        await w.cleanup()
