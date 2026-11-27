"""Debt reports (brief §29). Branch-scoped through branch_context: a
cashier always gets their own branch; global roles get all branches or the
one they pick. Credit-limit utilization uses all-branch figures, so only
global roles may see it."""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.customers import require_customer_reader
from app.core.authorization import branch_context
from app.core.dependencies import require_role
from app.db.session import get_db
from app.schemas.debt import (
    AgeingOut, BranchesReport, CollectionsReport, OpeningBalancesReport, OutstandingReport,
    OverdueReport, ReconciliationReport, UtilizationReport,
)
from app.services import debt_insights_service, debt_report_service
from app.services.report_service import _resolve_period_dates

router = APIRouter(prefix="/reports/debts", tags=["Debt reports"])

require_global_reader = require_role("super_admin", "admin", "general_manager")
require_old_debt_reader = require_role("super_admin", "admin", "cashier")


@router.get("/outstanding", response_model=OutstandingReport)
async def outstanding(branch_id: UUID | None = Depends(branch_context),
                      current_user=Depends(require_customer_reader), db: AsyncSession = Depends(get_db)):
    return await debt_report_service.outstanding(db, branch_id)


@router.get("/overdue", response_model=OverdueReport)
async def overdue(branch_id: UUID | None = Depends(branch_context),
                  current_user=Depends(require_customer_reader), db: AsyncSession = Depends(get_db)):
    return await debt_report_service.overdue(db, branch_id)


@router.get("/ageing", response_model=AgeingOut)
async def ageing(branch_id: UUID | None = Depends(branch_context),
                 current_user=Depends(require_customer_reader), db: AsyncSession = Depends(get_db)):
    return await debt_insights_service.ageing(db, branch_id)


@router.get("/collections", response_model=CollectionsReport)
async def collections(period: str = "month", from_date: date | None = None, to_date: date | None = None,
                      branch_id: UUID | None = Depends(branch_context),
                      current_user=Depends(require_customer_reader), db: AsyncSession = Depends(get_db)):
    date_from, date_to = _resolve_period_dates(period, from_date, to_date)
    return await debt_report_service.collections(db, branch_id, date_from, date_to)


@router.get("/branches", response_model=BranchesReport)
async def branches(period: str = "month", from_date: date | None = None, to_date: date | None = None,
                   branch_id: UUID | None = Depends(branch_context),
                   current_user=Depends(require_customer_reader), db: AsyncSession = Depends(get_db)):
    date_from, date_to = _resolve_period_dates(period, from_date, to_date)
    return await debt_report_service.branches(db, branch_id, date_from, date_to)


@router.get("/credit-utilization", response_model=UtilizationReport)
async def credit_utilization(current_user=Depends(require_global_reader), db: AsyncSession = Depends(get_db)):
    return await debt_report_service.credit_utilization(db)


@router.get("/opening-balances", response_model=OpeningBalancesReport)
async def opening_balances(status: Literal["pending", "approved", "rejected", "cancelled"] | None = None,
                           branch_id: UUID | None = Depends(branch_context),
                           current_user=Depends(require_old_debt_reader), db: AsyncSession = Depends(get_db)):
    return await debt_report_service.opening_balances(db, branch_id, status)


@router.get("/reconciliation", response_model=ReconciliationReport)
async def reconciliation(status: str | None = None, branch_id: UUID | None = None,
                         current_user=Depends(require_global_reader), db: AsyncSession = Depends(get_db)):
    from app.api.v1.reconciliation import parse_status
    return await debt_report_service.reconciliation(db, branch_id, parse_status(status))
