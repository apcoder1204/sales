from uuid import UUID
from datetime import datetime, timezone
import math
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.branch import Branch
from app.repositories.inventory_repo import inventory_repo
from app.repositories.product_repo import product_repo
from app.repositories.transfer_repo import transfer_repo
from app.schemas.transfer import (
    StockRequestCreate, DirectTransferCreate, StockRequestReview, StockRequestApprovalRequest
)
from app.core.exceptions import (
    InsufficientStockException, NotFoundException,
    TransferPermissionException, ValidationException
)
from app.services.audit_service import audit_service

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TransferService:
    async def create_request(
        self, db: AsyncSession, data: StockRequestCreate, user
    ):
        main_branch = await inventory_repo.get_main_store(db)

        products = {}
        for item_in in data.items:
            product = await product_repo.get_by_id(db, item_in.product_id)
            if not product:
                raise NotFoundException("Bidhaa")
            products[item_in.product_id] = product

        request_no = await transfer_repo.get_next_request_no(db)
        req = await transfer_repo.create_request(db, {
            "request_no": request_no,
            "requested_by": user.id,
            "from_branch_id": data.from_branch_id,
            "to_branch_id": data.to_branch_id,
            "reason": data.reason,
        })

        for item_in in data.items:
            main_inv = await inventory_repo.get_by_product_branch(
                db, item_in.product_id, main_branch.id
            ) if main_branch else None
            main_store_had_stock = (
                (main_inv.quantity - main_inv.reserved_qty) >= item_in.quantity
            ) if main_inv else False

            await transfer_repo.create_request_item(db, {
                "request_id": req.id,
                "product_id": item_in.product_id,
                "requested_qty": item_in.quantity,
                "main_store_had_stock": main_store_had_stock,
            })

        await db.commit()
        await db.refresh(req)
        await audit_service.log(
            db, action="TRANSFER_REQUEST_CREATED", category="transfers",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="stock_request", entity_id=str(req.id),
            details={
                "request_no": request_no,
                "items": [
                    {"product": products[i.product_id].name, "qty": i.quantity}
                    for i in data.items
                ],
            }
        )
        return req

    async def approve_request(
        self, db: AsyncSession, request_id: UUID, data: StockRequestApprovalRequest, user
    ):
        req = await transfer_repo.get_request_by_id(db, request_id)
        if not req:
            raise NotFoundException("Ombi")
        if req.status != "pending":
            raise ValidationException("Ombi hili haliwezi kuidhinishwa")

        items_by_id = {item.id: item for item in req.items}
        approvals: dict = {}
        for a in data.items:
            item = items_by_id.get(a.item_id)
            if not item:
                raise NotFoundException("Kipengele cha ombi")
            if a.approved_qty > item.requested_qty:
                raise ValidationException("Idadi iliyoidhinishwa haiwezi kuzidi iliyoombwa")
            approvals[a.item_id] = a.approved_qty
        if set(approvals.keys()) != set(items_by_id.keys()):
            raise ValidationException("Idhinisho la vipengele vyote vya ombi linahitajika")

        # Validate stock sufficiency for every approved-qty item before reserving anything.
        invs = {}
        for item in req.items:
            approved_qty = approvals[item.id]
            if approved_qty <= 0:
                continue
            inv = await inventory_repo.get_by_product_branch(db, item.product_id, req.from_branch_id)
            available = (inv.quantity - inv.reserved_qty) if inv else 0
            if available < approved_qty:
                raise InsufficientStockException(item.product.name, available, approved_qty)
            invs[item.id] = inv

        for item in req.items:
            approved_qty = approvals[item.id]
            if approved_qty > 0:
                inv = invs[item.id]
                await inventory_repo.update(db, inv.id, {
                    "reserved_qty": inv.reserved_qty + approved_qty
                })
            item.approved_qty = approved_qty
            item.status = "approved" if approved_qty > 0 else "rejected"
            item.reviewed_at = _utcnow()
            item.review_notes = data.notes

        req.status = "rejected" if all(approvals[i.id] == 0 for i in req.items) else "approved"
        req.reviewed_by = user.id
        req.reviewed_at = _utcnow()
        req.review_notes = data.notes
        await db.flush()
        await db.commit()

        await audit_service.log(
            db, action="TRANSFER_REQUEST_APPROVED", category="transfers",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="stock_request", entity_id=str(request_id),
            details={
                "request_no": req.request_no, "notes": data.notes,
                "items": [
                    {
                        "product": item.product.name,
                        "requested_qty": item.requested_qty,
                        "approved_qty": approvals[item.id],
                        "remaining": item.requested_qty - approvals[item.id],
                    }
                    for item in req.items
                ],
            }
        )
        return req

    async def _move_stock_item(
        self, db: AsyncSession, transfer_id: UUID,
        product_id: UUID, quantity: int,
        from_branch_id: UUID, to_branch_id: UUID, user_id: UUID,
        check_reserved: bool = True,
    ):
        """Locks source inventory, moves `quantity` units to the destination
        branch, and records the ledger entries + StockTransferItem line for
        one product. Raises InsufficientStockException if source lacks stock.

        `check_reserved` controls whether reserved_qty is subtracted from the
        stock-sufficiency check: direct transfers (no prior reservation) must
        check the true available quantity, while request execution checks raw
        quantity only — the amount was already reserved for this exact item
        at approval time and that reservation is released in this same call.
        """
        product = await product_repo.get_by_id(db, product_id)
        if not product:
            raise NotFoundException("Bidhaa")

        src = await inventory_repo.get_by_product_branch_locked(db, product_id, from_branch_id)
        checkable = ((src.quantity - src.reserved_qty) if check_reserved else src.quantity) if src else 0
        if checkable < quantity:
            raise InsufficientStockException(product.name, checkable, quantity)

        await inventory_repo.create_transaction(db, {
            "product_id": product_id, "branch_id": from_branch_id,
            "transaction_type": "transfer_out",
            "quantity_before": src.quantity,
            "quantity_change": -quantity,
            "quantity_after": src.quantity - quantity,
            "reference_id": transfer_id, "reference_type": "transfer",
            "performed_by": user_id,
        })
        src_update = {"quantity": src.quantity - quantity}
        if not check_reserved:
            # This quantity was reserved for this exact item at approval time —
            # release that reservation now that the stock has actually moved.
            src_update["reserved_qty"] = max(0, src.reserved_qty - quantity)
        await inventory_repo.update(db, src.id, src_update)

        dst = await inventory_repo.get_or_create(db, product_id, to_branch_id)
        await inventory_repo.create_transaction(db, {
            "product_id": product_id, "branch_id": to_branch_id,
            "transaction_type": "transfer_in",
            "quantity_before": dst.quantity,
            "quantity_change": quantity,
            "quantity_after": dst.quantity + quantity,
            "reference_id": transfer_id, "reference_type": "transfer",
            "performed_by": user_id,
        })
        await inventory_repo.update(db, dst.id, {"quantity": dst.quantity + quantity})

        await transfer_repo.create_transfer_item(db, {
            "transfer_id": transfer_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_cost": product.cost_price,
        })
        return product

    async def execute_request(
        self, db: AsyncSession, request_id: UUID, user
    ):
        req = await transfer_repo.get_request_by_id(db, request_id)
        if not req:
            raise NotFoundException("Ombi")
        if req.status != "approved":
            raise ValidationException("Ombi hili halijaidhinishwa bado")

        # Execution is a physical handover — only whoever holds the stock being
        # sent may confirm it: a cashier for their own branch, a store keeper
        # for Duka Kuu (main store). Managers approve/allocate but do not
        # execute — mirrors the existing main-store flow (manager approves,
        # store keeper executes) for POS-to-POS requests too.
        if user.role.name == "cashier" and str(user.branch_id) != str(req.from_branch_id):
            raise TransferPermissionException()
        if user.role.name == "store_keeper":
            from_branch = await db.get(Branch, req.from_branch_id)
            if not from_branch or from_branch.branch_type != "main_store":
                raise TransferPermissionException()

        approved_items = [i for i in req.items if i.status == "approved" and (i.approved_qty or 0) > 0]
        if not approved_items:
            raise ValidationException("Hakuna bidhaa zilizoidhinishwa za kutekeleza")

        moved = []
        async with db.begin_nested():
            transfer_no = await transfer_repo.get_next_transfer_no(db)
            tf = await transfer_repo.create_transfer(db, {
                "transfer_no": transfer_no,
                "request_id": req.id,
                "from_branch_id": req.from_branch_id,
                "to_branch_id": req.to_branch_id,
                "transferred_by": user.id,
                "status": "completed",
                "completed_at": _utcnow(),
                "notes": f"Utekelezaji wa {req.request_no}",
            })

            for item in approved_items:
                product = await self._move_stock_item(
                    db, tf.id, item.product_id, item.approved_qty,
                    req.from_branch_id, req.to_branch_id, user.id,
                    check_reserved=False,
                )
                item.status = "fulfilled"
                moved.append({
                    "product": product.name,
                    "requested_qty": item.requested_qty,
                    "approved_qty": item.approved_qty,
                    "remaining": item.requested_qty - item.approved_qty,
                })

            req.status = "fulfilled"
            req.reviewed_by = user.id
            req.reviewed_at = _utcnow()
            await db.flush()

        await db.commit()

        await audit_service.log(
            db, action="TRANSFER_REQUEST_FULFILLED", category="transfers",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="stock_request", entity_id=str(request_id),
            details={"request_no": req.request_no, "items": moved}
        )
        return req

    async def reject_request(
        self, db: AsyncSession, request_id: UUID, notes: str | None, user
    ):
        req = await transfer_repo.get_request_by_id(db, request_id)
        if not req:
            raise NotFoundException("Ombi")
        if req.status != "pending":
            raise ValidationException("Ombi hili haliwezi kukataliwa")

        req.status = "rejected"
        req.reviewed_by = user.id
        req.reviewed_at = _utcnow()
        req.review_notes = notes
        await db.flush()
        await db.commit()

        await audit_service.log(
            db, action="TRANSFER_REQUEST_REJECTED", category="transfers",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="stock_request", entity_id=str(request_id),
            details={"request_no": req.request_no, "notes": notes}
        )
        return req

    async def execute_transfer(
        self, db: AsyncSession, data: DirectTransferCreate, user
    ):
        if user.role.name == "store_keeper":
            from_branch = await db.get(
                __import__("app.models.branch", fromlist=["Branch"]).Branch,
                data.from_branch_id
            )
            if not from_branch or from_branch.branch_type != "main_store":
                raise TransferPermissionException()

        async with db.begin_nested():
            transfer_no = await transfer_repo.get_next_transfer_no(db)
            tf = await transfer_repo.create_transfer(db, {
                "transfer_no": transfer_no,
                "from_branch_id": data.from_branch_id,
                "to_branch_id": data.to_branch_id,
                "transferred_by": user.id,
                "status": "completed",
                "completed_at": _utcnow(),
                "notes": data.notes,
            })

            for item in data.items:
                await self._move_stock_item(
                    db, tf.id, item.product_id, item.quantity,
                    data.from_branch_id, data.to_branch_id, user.id,
                    check_reserved=True,
                )

        await db.commit()
        await db.refresh(tf)

        await audit_service.log(
            db, action="TRANSFER_COMPLETED", category="transfers",
            user_id=user.id, username=user.username, user_role=user.role.name,
            entity_type="stock_transfer", entity_id=str(tf.id),
            details={"transfer_no": transfer_no, "items": len(data.items)}
        )
        return tf

    def serialize_request(self, r) -> dict:
        # "Partial" is derived rather than stored: an item counts as partial
        # once it's been reviewed (approved_qty set) and got less than it
        # asked for — including a flat rejection (approved_qty == 0) while
        # sibling items in the same request went through.
        is_partial = r.status in ("approved", "fulfilled") and any(
            i.approved_qty is not None and i.approved_qty < i.requested_qty for i in r.items
        )
        return {
            "id": r.id, "request_no": r.request_no,
            "requested_by": r.requester.full_name,
            "from_branch": r.from_branch.name,
            "from_branch_id": r.from_branch_id,
            "to_branch": r.to_branch.name,
            "to_branch_id": r.to_branch_id,
            "items": [
                {
                    "id": i.id,
                    "product": i.product.name,
                    "product_code": i.product.product_code,
                    "product_id": i.product_id,
                    "requested_qty": i.requested_qty,
                    "approved_qty": i.approved_qty,
                    "item_status": i.status,
                    "main_store_had_stock": i.main_store_had_stock,
                }
                for i in r.items
            ],
            "items_count": len(r.items),
            "is_partial": is_partial,
            "reason": r.reason,
            "status": r.status,
            "reviewed_by": r.reviewer.full_name if r.reviewer else None,
            "reviewed_at": r.reviewed_at,
            "review_notes": r.review_notes,
            "created_at": r.created_at,
        }

    async def list_requests(
        self, db: AsyncSession, status: str | None,
        branch_id: UUID | None, page: int, per_page: int
    ):
        skip = (page - 1) * per_page
        rows, total = await transfer_repo.list_requests(db, status, branch_id, skip, per_page)
        items = [self.serialize_request(r) for r in rows]
        return {"items": items, "total": total, "page": page, "per_page": per_page,
                "pages": math.ceil(total / per_page) if total else 1}

    async def list_transfers(
        self, db: AsyncSession, from_branch_id: UUID | None,
        to_branch_id: UUID | None, page: int, per_page: int
    ):
        skip = (page - 1) * per_page
        rows, total = await transfer_repo.list_transfers(db, from_branch_id, to_branch_id, skip, per_page)
        items = [
            {
                "id": t.id,
                "transfer_no": t.transfer_no,
                "from_branch_name": t.from_branch.name,
                "to_branch_name": t.to_branch.name,
                "executed_by_name": t.executor.full_name,
                "items_count": len(t.items),
                "status": t.status,
                "notes": t.notes,
                "completed_at": t.completed_at,
                "created_at": t.created_at,
            }
            for t in rows
        ]
        return {"items": items, "total": total, "page": page, "per_page": per_page,
                "pages": math.ceil(total / per_page) if total else 1}


transfer_service = TransferService()
