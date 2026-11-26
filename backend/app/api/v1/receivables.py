"""Madeni Yote: every customer debt in one list (credit sales and approved
old debts), branch-scoped like the customer pages: a cashier sees only their
branch, the admin and general manager every branch or the one they pick."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customers import require_customer_reader
from app.db.session import get_db
from app.core.authorization import branch_context
from app.models.customer import Customer
from app.schemas.customer import CustomerRef
from app.schemas.debt import AgeingOut, DashboardOut
from app.schemas.payment import DebtListItem, DebtListResponse, DebtListSummary, ReceivableOut
from app.services import debt_insights_service, ledger_service
from app.services.report_service import _resolve_period_dates
from datetime import date

router = APIRouter(prefix="/receivables", tags=["Receivables"])

# OPEN = anything still owed (default); ALL includes paid ones.
StatusFilter = Literal["OPEN", "ALL", "UNPAID", "PARTIALLY_PAID", "OVERDUE", "PAID"]


@router.get("", response_model=DebtListResponse)
async def list_receivables(
    status: StatusFilter = "OPEN",
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    open_only = status not in ("ALL", "PAID")
    rows = await ledger_service.collect_receivables(db, branch_id=branch_id, search=q, open_only=open_only)
    if status not in ("OPEN", "ALL"):
        rows = [r for r in rows if r.status == status]

    owing = [r for r in rows if r.outstanding > 0]
    summary = DebtListSummary(
        total_outstanding=sum((r.outstanding for r in owing), Decimal("0.00")),
        overdue=sum((r.outstanding for r in owing if r.status == "OVERDUE"), Decimal("0.00")),
        customers_owing=len({r.customer_id for r in owing}),
    )
    page_rows = rows[(page - 1) * per_page: page * per_page]
    ids = {r.customer_id for r in page_rows}
    customers = {
        c.id: CustomerRef.model_validate(c)
        for c in (await db.execute(select(Customer).where(Customer.id.in_(ids)))).scalars()
    } if ids else {}
    items = [
        DebtListItem(**ReceivableOut.model_validate(r).model_dump(), customer=customers[r.customer_id])
        for r in page_rows
    ]
    return DebtListResponse(items=items, total=len(rows), summary=summary)


@router.get("/ageing", response_model=AgeingOut)
async def receivables_ageing(
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    return await debt_insights_service.ageing(db, branch_id)


@router.get("/dashboard", response_model=DashboardOut)
async def receivables_dashboard(
    period: str = "month",
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = Depends(branch_context),
    current_user=Depends(require_customer_reader),
    db: AsyncSession = Depends(get_db),
):
    date_from, date_to = _resolve_period_dates(period, from_date, to_date)
    return await debt_insights_service.dashboard(db, branch_id, date_from, date_to)
