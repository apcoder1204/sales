import math
from uuid import UUID
from datetime import datetime, date, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.branch import Branch
from sqlalchemy.exc import IntegrityError
from app.repositories.daily_closing_repo import daily_closing_repo
from app.repositories.sale_repo import sale_repo
from app.schemas.daily_closing import (
    CloseDayRequest, ClosingPreviewResponse, ClosingResponse, ExpenseResponse,
    OpenRegisterRequest,
)
from app.core.exceptions import NotFoundException, ValidationException, DuplicateException
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


def _window_for_register(existing, business_date: date) -> tuple[datetime, datetime]:
    """The time window a register's totals are computed over.

    A register opened explicitly via `open_register` (opened_at is set) is
    scoped to its own period — from when it opened until now — so sales
    taken under a *later* register are never folded into an earlier,
    already-reconciled one. A register that predates the opening-register
    feature (opened_at is NULL, e.g. the branch's very first-ever closing,
    or historical rows from before this feature existed) keeps the original
    whole-business-day window, preserving exact prior behavior for anyone
    who never explicitly opens a register."""
    if existing and existing.opened_at:
        # opened_at comes back from a TIMESTAMPTZ column as tz-aware; every
        # other timestamp compared against Sale.created_at in this codebase
        # (including _utcnow() below) is naive-but-UTC by convention — strip
        # tzinfo so both bounds are the same shape.
        return existing.opened_at.replace(tzinfo=None), _utcnow()
    return utc_range_for_business_date(business_date)


class DailyClosingService:
    async def preview(
        self, db: AsyncSession, branch_id: UUID, business_date: date | None
    ) -> ClosingPreviewResponse:
        business_date = business_date or business_date_today()
        branch = await db.get(Branch, branch_id)
        if not branch:
            raise NotFoundException("Tawi")

        existing = await daily_closing_repo.get_by_branch_date(db, branch_id, business_date)
        from_dt, to_dt = _window_for_register(existing, business_date)
        totals = await sale_repo.get_totals_by_payment_method(db, branch_id, from_dt, to_dt)

        return ClosingPreviewResponse(
            branch_id=branch_id, branch_name=branch.name, business_date=business_date,
            already_closed=bool(existing and existing.status == "closed"),
            register_number=existing.register_number if existing else 1,
            register_open=bool(existing and existing.status == "open"),
            opened_by=existing.opener.full_name if existing and existing.opener else None,
            opened_at=existing.opened_at if existing else None,
            opening_cash=existing.opening_cash if existing else None,
            total_cash=totals["cash"], total_mobile_money=totals["mobile_money"],
            total_bank_transfer=totals["bank_transfer"],
            total_sales_count=totals["count"], total_revenue=totals["revenue"],
        )

    async def open_register(self, db: AsyncSession, data: OpenRegisterRequest, user):
        business_date = data.business_date or business_date_today()
        branch = await db.get(Branch, data.branch_id)
        if not branch:
            raise NotFoundException("Tawi")
        if not branch.is_active:
            raise ValidationException("Tawi hili halifanyi kazi kwa sasa")

        if await daily_closing_repo.get_open_register(db, data.branch_id):
            raise ValidationException("Tawi hili tayari lina rejista iliyo wazi")

        next_number = await daily_closing_repo.get_max_register_number(
            db, data.branch_id, business_date
        ) + 1

        payload = {
            "branch_id": data.branch_id, "business_date": business_date,
            "register_number": next_number, "status": "open",
            "opened_by": user.id, "opened_at": _utcnow(),
            "opening_cash": data.opening_cash,
        }
        try:
            async with db.begin_nested():
                register = await daily_closing_repo.create(db, payload)
        except IntegrityError as exc:
            # Two concurrent open-register calls for the same branch: only
            # one can win uq_daily_closing_one_open_per_branch — the loser
            # lands here instead of a raw 500.
            raise DuplicateException("Rejista iliyo wazi kwa tawi hili") from exc

        await db.commit()
        await audit_service.log(
            db, action="REGISTER_OPENED", category="sales",
            user_id=user.id, username=user.username, user_role=user.role.name,
            branch_id=data.branch_id, entity_type="daily_closing", entity_id=str(register.id),
            details={
                "business_date": str(business_date), "register_number": next_number,
                "opening_cash": float(data.opening_cash),
            },
        )
        return register

    async def close_day(self, db: AsyncSession, data: CloseDayRequest, user):
        business_date = data.business_date or business_date_today()
        branch = await db.get(Branch, data.branch_id)
        if not branch:
            raise NotFoundException("Tawi")

        existing = await daily_closing_repo.get_by_branch_date(db, data.branch_id, business_date)
        if existing and existing.status == "closed":
            raise ValidationException("Siku hii tayari imefungwa kwa tawi hili")

        from_dt, to_dt = _window_for_register(existing, business_date)
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
        try:
            async with db.begin_nested():
                if existing:
                    # Re-closing (e.g. after a reopen) replaces the prior
                    # reconciliation entirely — old matumizi rows no longer
                    # apply to this closing.
                    await daily_closing_repo.delete_expenses(db, existing.id)
                    closing = await daily_closing_repo.update(db, existing.id, payload)
                else:
                    closing = await daily_closing_repo.create(db, payload)

                for e in data.expenses:
                    await daily_closing_repo.create_expense(db, {
                        "closing_id": closing.id, "description": e.description, "amount": e.amount,
                    })
        except IntegrityError as exc:
            # Two concurrent close_day calls for the same (branch_id,
            # business_date) with no existing row yet: both pass the
            # `existing is None` check above, only one INSERT can win the
            # unique constraint — the loser lands here instead of a raw 500.
            raise DuplicateException("Kufunga kwa siku hii") from exc

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

        # A branch may have at most one OPEN register at a time — if a
        # newer register was already opened for this branch (the normal
        # post-closing flow), reopening this older one would create a
        # second simultaneously-open register, which uq_daily_closing_one_
        # open_per_branch forbids at the DB level. Surface that clearly
        # rather than letting it fail as a raw IntegrityError.
        other_open = await daily_closing_repo.get_open_register(db, closing.branch_id)
        if other_open and other_open.id != closing.id:
            raise ValidationException(
                "Tawi hili tayari lina rejista nyingine iliyo wazi. Ifunge kwanza."
            )

        closing.status = "open"
        closing.reopened_by = user.id
        closing.reopened_at = _utcnow()
        closing.reopen_reason = reason
        try:
            await db.flush()
        except IntegrityError as exc:
            raise DuplicateException("Rejista iliyo wazi kwa tawi hili") from exc
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
            business_date=c.business_date, register_number=c.register_number, status=c.status,
            opened_by=c.opener.full_name if c.opener else None, opened_at=c.opened_at,
            opening_cash=c.opening_cash,
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
