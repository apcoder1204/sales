from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.customer import Customer
from app.models.payment import Payment, PaymentAllocation
from app.services import ledger_service, payment_service
from app.repositories.inventory_repo import inventory_repo
from app.repositories.product_repo import product_repo
from app.repositories.sale_repo import sale_repo
from app.repositories.daily_closing_repo import daily_closing_repo
from app.schemas.sale import (
    SaleCreate, ReceiptData, ReceiptPaymentLine, SaleItemResponse, SalePaymentOut,
)
from app.core.exceptions import (
    InsufficientStockException, NotFoundException, ValidationException, debt_error,
)
from app.services.audit_service import audit_service
from app.core.business_time import business_date_today, business_date_for

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fmt(amount: Decimal) -> str:
    return f"{settings.CURRENCY} {int(amount):,}"


def _method_label(method: str) -> str:
    return method.replace("_", " ").title()


@dataclass
class SalePaymentView:
    """What a sale's payments add up to — derived from its allocations."""
    payments: list[SalePaymentOut]
    receipt_lines: list[ReceiptPaymentLine]
    paid: Decimal
    outstanding: Decimal
    payment_status: str
    payment_method: str | None
    payment_reference: str | None


def sale_payment_view(sale) -> SalePaymentView:
    allocs = sorted(sale.payment_allocations, key=lambda a: a.payment.payment_no)
    active = [a for a in allocs if a.payment.status == "active"]
    paid = sum((a.amount for a in active), Decimal("0.00"))
    if sale.status == "voided":
        outstanding, status = Decimal("0.00"), "VOIDED"
    else:
        outstanding = sale.total_amount - paid
        status = ledger_service.receivable_status(
            sale.total_amount, outstanding, sale.due_date, business_date_today()
        )
    # Sale-time payments: the active ones, or all of them on a voided sale
    # (whose payments were reversed by the void).
    till = [
        a.payment for a in allocs
        if a.payment.kind == "sale" and (a.payment.status == "active" or sale.status == "voided")
    ]
    if not till:
        method = sale.payment_method or "credit"  # legacy row never backfilled
        reference = sale.payment_reference
    else:
        method = till[0].method if len(till) == 1 else "mixed"
        reference = till[0].reference
    return SalePaymentView(
        payments=[
            SalePaymentOut(
                id=a.payment.id, payment_no=a.payment.payment_no, kind=a.payment.kind,
                method=a.payment.method, amount=a.amount, reference=a.payment.reference,
                status=a.payment.status, created_at=a.payment.created_at,
            )
            for a in allocs
        ],
        receipt_lines=[
            ReceiptPaymentLine(method=_method_label(p.method), amount=_fmt(p.amount), reference=p.reference)
            for p in till
        ],
        paid=paid, outstanding=outstanding, payment_status=status,
        payment_method=method, payment_reference=reference,
    )


class SaleService:
    async def create_sale(
        self, db: AsyncSession, data: SaleCreate, cashier
    ) -> tuple:
        closing = await daily_closing_repo.get_by_branch_date(db, data.branch_id, business_date_today())
        if closing and closing.status == "closed":
            raise ValidationException(
                "Siku hii tayari imefungwa kwa tawi hili. Wasiliana na msimamizi kufungua tena.",
                "DAY_ALREADY_CLOSED",
            )

        # --- Phase 1: validate products (no DB locks yet — fail fast) ---
        products: dict[UUID, object] = {}
        for item_in in data.items:
            product = await product_repo.get_by_id(db, item_in.product_id)
            if not product or product.status != "active":
                raise NotFoundException("Bidhaa", "product")
            products[item_in.product_id] = product

        # Calculate financials from locked-in product prices
        subtotal = sum(
            products[i.product_id].selling_price * i.quantity
            for i in data.items
        )
        total_amount = subtotal

        # Payment lines: legacy single-method payload pays the full total.
        if data.is_legacy:
            lines = [(data.payment_method, total_amount, data.payment_reference)]
        else:
            lines = [(p.method, p.amount, p.reference) for p in data.payments]
        paid = sum((amt for _, amt, _ in lines), Decimal("0"))
        if paid > total_amount:
            raise debt_error("PAYMENT_EXCEEDS_TOTAL")
        outstanding = total_amount - paid
        if outstanding > 0 and data.customer_id is None:
            raise debt_error("CREDIT_REQUIRES_CUSTOMER")
        today = business_date_today()

        # --- Phase 2: atomic transaction with row-level locks ---
        async with db.begin_nested():
            customer, due_date = await self._authorize_credit(db, data.customer_id, outstanding, today)

            transaction_no = await sale_repo.get_next_transaction_no(db)

            sale = await sale_repo.create_sale(db, {
                "transaction_no": transaction_no,
                "branch_id": data.branch_id,
                "cashier_id": cashier.id,
                "subtotal": subtotal,
                "total_amount": total_amount,
                "customer_id": customer.id if customer else None,
                "due_date": due_date,
                "notes": data.notes,
            })

            for item_in in data.items:
                product = products[item_in.product_id]

                # Lock the inventory row inside the savepoint so concurrent
                # sales cannot double-spend the same stock.
                inv = await inventory_repo.get_by_product_branch_locked(
                    db, item_in.product_id, data.branch_id
                )
                available = (inv.quantity - inv.reserved_qty) if inv else 0
                if available < item_in.quantity:
                    raise InsufficientStockException(product.name, available, item_in.quantity)

                qty_before = inv.quantity
                qty_after = qty_before - item_in.quantity

                await inventory_repo.create_transaction(db, {
                    "product_id": product.id,
                    "branch_id": data.branch_id,
                    "transaction_type": "sale",
                    "quantity_before": qty_before,
                    "quantity_change": -item_in.quantity,
                    "quantity_after": qty_after,
                    "reference_id": sale.id,
                    "reference_type": "sale",
                    "performed_by": cashier.id,
                })
                await inventory_repo.update(db, inv.id, {"quantity": qty_after})

                await sale_repo.create_sale_item(db, {
                    "sale_id": sale.id,
                    "product_id": product.id,
                    "quantity": item_in.quantity,
                    "unit_price": product.selling_price,
                    "cost_price": product.cost_price,
                    "line_total": product.selling_price * item_in.quantity,
                })

            payments = []
            for method, amount, reference in lines:
                payment = Payment(
                    payment_no=await payment_service.next_payment_no(db), kind="sale",
                    customer_id=customer.id if customer else None, branch_id=data.branch_id,
                    method=method, reference=reference, amount=amount, business_date=today,
                    received_by=cashier.id, status="active",
                )
                db.add(payment)
                await db.flush()
                db.add(PaymentAllocation(payment_id=payment.id, sale_id=sale.id, amount=amount))
                payments.append(payment)
            await db.flush()

            if customer:
                await ledger_service.post(
                    db, customer_id=customer.id, branch_id=data.branch_id, entry_type="sale",
                    source_type="sale", source_id=sale.id, business_date=today,
                    debit=total_amount, due_date=due_date,
                    description=f"Mauzo {transaction_no}", created_by=cashier.id,
                )
                for payment in payments:
                    await ledger_service.post(
                        db, customer_id=customer.id, branch_id=data.branch_id,
                        entry_type="payment", source_type="payment", source_id=payment.id,
                        business_date=today, credit=payment.amount,
                        description=f"Malipo {payment.payment_no} ({transaction_no})",
                        created_by=cashier.id,
                    )

        await db.commit()
        await db.refresh(sale)

        await audit_service.log(
            db, action="SALE_CREATED", category="sales",
            user_id=cashier.id, username=cashier.username, user_role=cashier.role.name,
            branch_id=data.branch_id, entity_type="sale", entity_id=str(sale.id),
            details={
                "transaction_no": transaction_no,
                "total": str(total_amount),
                "items_count": len(data.items),
                "customer_id": str(customer.id) if customer else None,
                "payments": [{"method": m, "amount": str(a)} for m, a, _ in lines],
                "credit_amount": str(outstanding),
            },
        )

        receipt = self._build_receipt(sale, cashier)
        return sale, receipt

    async def _authorize_credit(
        self, db: AsyncSession, customer_id: UUID | None, outstanding: Decimal, today: date
    ) -> tuple[Customer | None, date | None]:
        """Decision D3: credit only to a registered active customer within the
        admin-set limit, which is one total across all branches (D4). The
        customer row lock serializes concurrent credit decisions."""
        if outstanding <= 0:
            if customer_id is None:
                return None, None
            customer = await db.get(Customer, customer_id)
            if not customer:
                raise NotFoundException("Mteja", "customer")
            return customer, None
        customer = await ledger_service.lock_customer(db, customer_id)
        if customer.status != "active":
            raise debt_error("CUSTOMER_INACTIVE")
        if customer.credit_limit <= 0:
            raise debt_error("CREDIT_NOT_ALLOWED")
        current = await ledger_service.customer_balance(db, customer.id)
        if current + outstanding > customer.credit_limit:
            raise debt_error("CREDIT_LIMIT_EXCEEDED", {
                "limit": str(int(customer.credit_limit)),
                "current": str(int(current)),
                "requested": str(int(outstanding)),
                "available": str(int(max(Decimal("0"), customer.credit_limit - current))),
            })
        return customer, today + timedelta(days=customer.credit_days)

    async def get_sale_for_viewing(self, db: AsyncSession, sale_id: UUID, user):
        """Shared authorization for both GET /sales/{id} and its /receipt
        sibling — a cashier may only look up their own sales, everyone else
        follows the same unrestricted-by-role convention list_sales already
        uses (branch scoping there comes from branch_context, not a role
        check)."""
        sale = await sale_repo.get_by_id(db, sale_id)
        if not sale:
            raise NotFoundException("Muamala", "sale")
        if user.role.name == "cashier" and sale.cashier_id != user.id:
            raise NotFoundException("Muamala", "sale")
        return sale

    def get_receipt(self, sale) -> ReceiptData:
        return self._build_receipt(sale, sale.cashier)

    def _build_receipt(self, sale, cashier) -> ReceiptData:
        items = [
            SaleItemResponse(
                id=i.id,
                product_id=i.product_id,
                product=i.product.name,
                quantity=i.quantity,
                unit_price=i.unit_price,
                cost_price=i.cost_price,
                line_total=i.line_total,
            )
            for i in sale.items
        ]
        view = sale_payment_view(sale)
        return ReceiptData(
            transaction_no=sale.transaction_no,
            branch_name=sale.branch.name,
            cashier_name=cashier.full_name,
            date=sale.created_at.strftime("%d/%m/%Y %H:%M"),
            items=items,
            subtotal=_fmt(sale.subtotal),
            total_amount=_fmt(sale.total_amount),
            payment_method=_method_label(view.payment_method),
            payment_reference=view.payment_reference,
            customer_name=sale.customer.name if sale.customer else None,
            payments=view.receipt_lines,
            paid=_fmt(view.paid),
            balance=_fmt(view.outstanding) if view.outstanding > 0 else None,
            due_date=sale.due_date.strftime("%d/%m/%Y") if sale.due_date and view.outstanding > 0 else None,
        )

    async def void_sale(self, db: AsyncSession, sale_id: UUID, reason: str, user):
        async with db.begin_nested():
            # Lock the sale row so two concurrent void requests for the same
            # sale can't both pass the status check and both restore stock.
            sale = await sale_repo.get_by_id_locked(db, sale_id)
            if not sale:
                raise NotFoundException("Muamala", "sale")
            if sale.status != "completed":
                raise ValidationException("Muamala huu tayari umebatilishwa", "SALE_ALREADY_VOIDED")

            closing = await daily_closing_repo.get_by_branch_date(
                db, sale.branch_id, business_date_for(sale.created_at)
            )
            if closing and closing.status == "closed":
                raise ValidationException(
                    "Siku ya muamala huu tayari imefungwa. Wasiliana na msimamizi kufungua tena.",
                    "DAY_ALREADY_CLOSED",
                )

            items = list(sale.items)
            restored = []
            # Lock inventory rows in a deterministic order (by product_id) —
            # reduces deadlock risk against a concurrent sale/adjustment/void
            # touching overlapping products at the same branch.
            for item in sorted(items, key=lambda i: str(i.product_id)):
                inv = await inventory_repo.get_by_product_branch_locked(
                    db, item.product_id, sale.branch_id
                )
                if not inv:
                    # A sold item must have had an inventory row at the time
                    # of sale — a missing row here means the data is already
                    # inconsistent. Surface it loudly rather than silently
                    # fabricating a new row with a guessed quantity.
                    raise ValidationException(
                        "Hifadhi ya bidhaa haikupatikana kwa ajili ya kurejesha hisa",
                        "INVENTORY_ROW_MISSING",
                    )
                qty_before = inv.quantity
                qty_after = qty_before + item.quantity
                await inventory_repo.create_transaction(db, {
                    "product_id": item.product_id,
                    "branch_id": sale.branch_id,
                    "transaction_type": "stock_in",
                    "quantity_before": qty_before,
                    "quantity_change": item.quantity,
                    "quantity_after": qty_after,
                    "reference_id": sale.id,
                    "reference_type": "sale_void",
                    "notes": f"Kurejesha hisa baada ya kubatilisha muamala: {reason}",
                    "performed_by": user.id,
                })
                await inventory_repo.update(db, inv.id, {"quantity": qty_after})
                restored.append({"product_id": str(item.product_id), "quantity": item.quantity})

            await sale_repo.update(db, sale_id, {
                "status": "voided",
                "voided_by": user.id,
                "voided_at": _utcnow(),
                "void_reason": reason,
            })
            await db.flush()

        await db.commit()
        await audit_service.log(
            db, action="SALE_VOIDED", category="sales",
            user_id=user.id, username=user.username, user_role=user.role.name,
            branch_id=sale.branch_id, entity_type="sale", entity_id=str(sale_id),
            details={
                "transaction_no": sale.transaction_no, "reason": reason,
                "items_restored": restored,
            },
        )


sale_service = SaleService()
