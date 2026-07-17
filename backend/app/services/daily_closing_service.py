import math
from uuid import UUID
from datetime import datetime, date, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.branch import Branch
from app.repositories.daily_closing_repo import daily_closing_repo
from app.repositories.sale_repo import sale_repo
from app.schemas.daily_closing import CloseDayRequest, ClosingPreviewResponse, ClosingResponse, ExpenseResponse
from app.core.exceptions import NotFoundException, ValidationException
from app.services.audit_service import audit_service

UTC = timezone.utc
_TZ = ZoneInfo(settings.DEFAULT_TIMEZONE)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def business_date_today() -> date:
    return datetime.now(_TZ).date()


def business_date_for(naive_utc_dt: datetime) -> date:
    """Convert a naive-UTC timestamp (as stored on Sale.created_at) to the
    local business date it falls on."""
    return naive_utc_dt.replace(tzinfo=UTC).astimezone(_TZ).date()


def utc_range_for_business_date(business_date: date) -> tuple[datetime, datetime]:
    """Sale.created_at is stored as naive UTC, but a "business day" is defined
    in the branch's local timezone — convert the local midnight-to-midnight
    window to naive UTC bounds so late-night local sales aren't attributed to
    the wrong calendar day."""
    start_local = datetime.combine(business_date, time.min, tzinfo=_TZ)
    end_local = datetime.combine(business_date, time.max, tzinfo=_TZ)
    return (
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )


class DailyClosingService:
    async def preview(
        self, db: AsyncSession, branch_id: UUID, business_date: date | None
    ) -> ClosingPreviewResponse:
        business_date = business_date or business_date_today()
        branch = await db.get(Branch, branch_id)
        if not branch:
            raise NotFoundException("Tawi")

        existing = await daily_closing_repo.get_by_branch_date(db, branch_id, business_date)
        from_dt, to_dt = utc_range_for_business_date(business_date)
        totals = await sale_repo.get_totals_by_payment_method(db, branch_id, from_dt, to_dt)

        return ClosingPreviewResponse(
            branch_id=branch_id, branch_name=branch.name, business_date=business_date,
            already_closed=bool(existing and existing.status == "closed"),
            total_cash=totals["cash"], total_mobile_money=totals["mobile_money"],
            total_bank_transfer=totals["bank_transfer"],
            total_sales_count=totals["count"], total_revenue=totals["revenue"],
        )

    async def close_day(self, db: AsyncSession, data: CloseDayRequest, user):
        business_date = data.business_date or business_date_today()
        branch = await db.get(Branch, data.branch_id)
        if not branch:
            raise NotFoundException("Tawi")

        existing = await daily_closing_repo.get_by_branch_date(db, data.branch_id, business_date)
        if existing and existing.status == "closed":
            raise ValidationException("Siku hii tayari imefungwa kwa tawi hili")

        from_dt, to_dt = utc_range_for_business_date(business_date)
        totals = await sale_repo.get_totals_by_payment_method(db, data.branch_id, from_dt, to_dt)

        # "Matumizi" entries explain a cash variance, in whichever direction it
        # runs: for a SHORTAGE (counted < system cash) they're money paid out of
        # the drawer during the day, so they reduce the cash we'd expect to find
        # — netting the shortage back toward zero. For a SURPLUS (counted >
        # system cash) they instead explain where the extra came from (e.g. a
        # customer's unclaimed change), so they net the surplus down instead.
        # Same {description, amount} shape either way — only the netting sign
        # depends on the *raw* variance direction before any matumizi applied.
        total_expenses = sum((e.amount for e in data.expenses), Decimal("0"))
        cash_variance = None
        if data.counted_cash is not None:
            raw_variance = data.counted_cash - Decimal(str(totals["cash"]))
            cash_variance = raw_variance + total_expenses if raw_variance < 0 else raw_variance - total_expenses

        payload = {
            "branch_id": data.branch_id, "business_date": business_date,
            "status": "closed",
            "total_cash": totals["cash"], "total_mobile_money": totals["mobile_money"],
            "total_bank_transfer": totals["bank_transfer"],
            "total_sales_count": totals["count"], "total_revenue": totals["revenue"],
            "counted_cash": data.counted_cash, "cash_variance": cash_variance,
            "closing_notes": data.notes,
            "closed_by": user.id, "closed_at": _utcnow(),
        }
        if existing:
            # Re-closing (e.g. after a reopen) replaces the prior reconciliation
            # entirely — old matumizi rows no longer apply to this closing.
            await daily_closing_repo.delete_expenses(db, existing.id)
            closing = await daily_closing_repo.update(db, existing.id, payload)
        else:
            closing = await daily_closing_repo.create(db, payload)

        for e in data.expenses:
            await daily_closing_repo.create_expense(db, {
                "closing_id": closing.id, "description": e.description, "amount": e.amount,
            })

        await db.commit()
        # This session uses expire_on_commit=False, so `closing.expenses` (already
        # loaded — possibly as empty — earlier in this same call) would otherwise
        # stay stale in the identity map. Force just that relationship to reload.
        await db.refresh(closing, attribute_names=["expenses"])

        await audit_service.log(
            db, action="DAY_CLOSED", category="sales",
            user_id=user.id, username=user.username, user_role=user.role.name,
            branch_id=data.branch_id, entity_type="daily_closing", entity_id=str(closing.id),
            details={
                "business_date": str(business_date),
                "total_cash": totals["cash"], "total_mobile_money": totals["mobile_money"],
                "total_bank_transfer": totals["bank_transfer"], "total_revenue": totals["revenue"],
                "counted_cash": float(data.counted_cash) if data.counted_cash is not None else None,
                "cash_variance": float(cash_variance) if cash_variance is not None else None,
                "expenses": [{"description": e.description, "amount": float(e.amount)} for e in data.expenses],
            }
        )
        return closing

    async def reopen(self, db: AsyncSession, closing_id: UUID, reason: str, user):
        closing = await daily_closing_repo.get_by_id(db, closing_id)
        if not closing:
            raise NotFoundException("Kufunga kwa Siku")
        if closing.status != "closed":
            raise ValidationException("Siku hii haijafungwa")

        closing.status = "open"
        closing.reopened_by = user.id
        closing.reopened_at = _utcnow()
        closing.reopen_reason = reason
        await db.flush()
        await db.commit()
        await db.refresh(closing)

        await audit_service.log(
            db, action="DAY_REOPENED", category="sales",
            user_id=user.id, username=user.username, user_role=user.role.name,
            branch_id=closing.branch_id, entity_type="daily_closing", entity_id=str(closing.id),
            details={"business_date": str(closing.business_date), "reason": reason}
        )
        return closing

    def serialize(self, c) -> ClosingResponse:
        return ClosingResponse(
            id=c.id, branch_id=c.branch_id, branch_name=c.branch.name,
            business_date=c.business_date, status=c.status,
            total_cash=c.total_cash, total_mobile_money=c.total_mobile_money,
            total_bank_transfer=c.total_bank_transfer,
            total_sales_count=c.total_sales_count, total_revenue=c.total_revenue,
            counted_cash=c.counted_cash, cash_variance=c.cash_variance,
            total_expenses=sum((e.amount for e in c.expenses), Decimal("0")),
            expenses=[ExpenseResponse(id=e.id, description=e.description, amount=e.amount) for e in c.expenses],
            closing_notes=c.closing_notes,
            closed_by=c.closer.full_name if c.closer else None, closed_at=c.closed_at,
            reopened_by=c.reopener.full_name if c.reopener else None, reopened_at=c.reopened_at,
            reopen_reason=c.reopen_reason, created_at=c.created_at,
        )

    async def list_closings(
        self, db: AsyncSession,
        branch_id: UUID | None, from_date: date | None, to_date: date | None,
        page: int, per_page: int
    ):
        skip = (page - 1) * per_page
        rows, total = await daily_closing_repo.list_closings(db, branch_id, from_date, to_date, skip, per_page)
        items = [self.serialize(r) for r in rows]
        return {"items": items, "total": total, "page": page, "per_page": per_page,
                "pages": math.ceil(total / per_page) if total else 1}


daily_closing_service = DailyClosingService()
