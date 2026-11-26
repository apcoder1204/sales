"""Stage 2 read models: statements, ageing, dashboard, risk, follow-ups and
debt reports. All amounts are Decimal; nothing here writes money."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.customer import CustomerRef


class StatementLine(BaseModel):
    date: date
    reference: str
    description: str
    entry_type: str
    branch_name: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class StatementOut(BaseModel):
    customer: CustomerRef
    branch_id: UUID | None
    date_from: date
    date_to: date
    opening_balance: Decimal
    lines: list[StatementLine]
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal


class AgeingRow(BaseModel):
    customer: CustomerRef
    buckets: dict[str, Decimal]
    total: Decimal


class BranchAgeing(BaseModel):
    branch_id: UUID
    branch_name: str
    buckets: dict[str, Decimal]
    total: Decimal


class AgeingOut(BaseModel):
    rows: list[AgeingRow]
    totals: dict[str, Decimal]
    total: Decimal
    by_branch: list[BranchAgeing]


class OldestDebt(BaseModel):
    customer: CustomerRef
    reference: str
    date: date
    days_overdue: int
    outstanding: Decimal


class TopDebtor(BaseModel):
    customer: CustomerRef
    outstanding: Decimal
    overdue: Decimal


class DashboardOut(BaseModel):
    total_outstanding: Decimal
    customers_owing: int
    overdue_total: Decimal
    collected_in_period: Decimal
    customers_over_limit: int
    oldest_debt: OldestDebt | None
    ageing: dict[str, Decimal]
    top_debtors: list[TopDebtor]
