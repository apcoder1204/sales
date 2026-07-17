from decimal import Decimal
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.repositories.inventory_repo import inventory_repo
from app.repositories.product_repo import product_repo
from app.repositories.sale_repo import sale_repo
from app.repositories.daily_closing_repo import daily_closing_repo
from app.schemas.sale import SaleCreate, ReceiptData, SaleItemResponse
from app.core.exceptions import InsufficientStockException, NotFoundException, ValidationException
from app.services.audit_service import audit_service
from app.services.daily_closing_service import business_date_today, business_date_for

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fmt(amount: Decimal) -> str:
    return f"{settings.CURRENCY} {int(amount):,}"


class SaleService:
    async def create_sale(
        self, db: AsyncSession, data: SaleCreate, cashier
    ) -> tuple:
        closing = await daily_closing_repo.get_by_branch_date(db, data.branch_id, business_date_today())
        if closing and closing.status == "closed":
            raise ValidationException("Siku hii tayari imefungwa kwa tawi hili. Wasiliana na msimamizi kufungua tena.")

        # --- Phase 1: validate products (no DB locks yet — fail fast) ---
        products: dict[UUID, object] = {}
        for item_in in data.items:
            product = await product_repo.get_by_id(db, item_in.product_id)
            if not product or product.status != "active":
                raise NotFoundException("Bidhaa")
            products[item_in.product_id] = product

        # Calculate financials from locked-in product prices
        subtotal = sum(
            products[i.product_id].selling_price * i.quantity
            for i in data.items
        )
        total_amount = subtotal

        # --- Phase 2: atomic transaction with row-level locks ---
        async with db.begin_nested():
            transaction_no = await sale_repo.get_next_transaction_no(db)

            sale = await sale_repo.create_sale(db, {
                "transaction_no": transaction_no,
                "branch_id": data.branch_id,
                "cashier_id": cashier.id,
                "subtotal": subtotal,
                "total_amount": total_amount,
                "payment_method": data.payment_method,
                "payment_reference": data.payment_reference,
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
                "payment_method": data.payment_method,
            },
        )

        receipt = self._build_receipt(sale, cashier)
        return sale, receipt

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
        return ReceiptData(
            transaction_no=sale.transaction_no,
            branch_name=sale.branch.name,
            cashier_name=cashier.full_name,
            date=sale.created_at.strftime("%d/%m/%Y %H:%M"),
            items=items,
            subtotal=_fmt(sale.subtotal),
            total_amount=_fmt(sale.total_amount),
            payment_method=sale.payment_method.replace("_", " ").title(),
            payment_reference=sale.payment_reference,
        )

    async def void_sale(self, db: AsyncSession, sale_id: UUID, reason: str, user):
        sale = await sale_repo.get_by_id(db, sale_id)
        if not sale:
            raise NotFoundException("Muamala")
        if sale.status == "voided":
            raise ValidationException("Muamala huu tayari umebatilishwa")

        closing = await daily_closing_repo.get_by_branch_date(
            db, sale.branch_id, business_date_for(sale.created_at)
        )
        if closing and closing.status == "closed":
            raise ValidationException("Siku ya muamala huu tayari imefungwa. Wasiliana na msimamizi kufungua tena.")

        await sale_repo.update(db, sale_id, {
            "status": "voided",
            "voided_by": user.id,
            "voided_at": _utcnow(),
            "void_reason": reason,
        })
        await db.commit()
        await audit_service.log(
            db, action="SALE_VOIDED", category="sales",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="sale", entity_id=str(sale_id),
            details={"transaction_no": sale.transaction_no, "reason": reason},
        )


sale_service = SaleService()
