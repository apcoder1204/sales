"""Stage 2 read models: statements, ageing, dashboard, risk, follow-ups and
debt reports. All amounts are Decimal; nothing here writes money."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError

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


class FollowUpCreate(BaseModel):
    # Cashiers always note for their own branch; the admin must choose one.
    branch_id: UUID | None = None
    contact_date: date
    method: Literal["phone", "visit", "sms", "whatsapp"]
    note: str = Field(min_length=3, max_length=1000)
    expected_payment_date: date | None = None

    @model_validator(mode="after")
    def contact_not_in_future(self):
        from app.core.business_time import business_date_today

        if self.contact_date > business_date_today():
            raise PydanticCustomError("contact_date_future", "Tarehe ya mawasiliano haiwezi kuwa ya baadaye")
        return self


class FollowUpOut(BaseModel):
    id: UUID
    branch_id: UUID
    branch_name: str
    contact_date: date
    method: str
    note: str
    expected_payment_date: date | None
    responsible_user_name: str
    created_at: datetime


# ---- Debt reports (brief §29) ----

class OutstandingRow(BaseModel):
    customer: CustomerRef
    balance: Decimal
    overdue: Decimal
    credit_limit: Decimal
    last_payment_at: datetime | None
    flags: list[str]


class OutstandingSummary(BaseModel):
    total_balance: Decimal
    total_overdue: Decimal
    customers: int


class OutstandingReport(BaseModel):
    rows: list[OutstandingRow]
    summary: OutstandingSummary


class OverdueRow(BaseModel):
    customer: CustomerRef
    branch_name: str
    reference: str
    due_date: date
    days_overdue: int
    outstanding: Decimal


class CountTotal(BaseModel):
    total: Decimal
    count: int


class OverdueReport(BaseModel):
    rows: list[OverdueRow]
    summary: CountTotal


class CollectionRow(BaseModel):
    payment_no: str
    business_date: date
    customer: CustomerRef
    branch_name: str
    method: str
    amount: Decimal
    received_by: str


class CollectionSummary(CountTotal):
    by_method: dict[str, Decimal]


class CollectionsReport(BaseModel):
    rows: list[CollectionRow]
    summary: CollectionSummary


class BranchRow(BaseModel):
    branch_id: UUID
    branch_name: str
    outstanding: Decimal
    overdue: Decimal
    customers_owing: int
    collected_in_period: Decimal


class BranchSummary(BaseModel):
    outstanding: Decimal
    overdue: Decimal
    customers_owing: int
    collected_in_period: Decimal


class BranchesReport(BaseModel):
    rows: list[BranchRow]
    summary: BranchSummary


class UtilizationRow(BaseModel):
    customer: CustomerRef
    credit_limit: Decimal
    balance: Decimal
    used_pct: Decimal | None
    available: Decimal
    flags: list[str]


class UtilizationSummary(BaseModel):
    customers_over_limit: int
    customers_near_limit: int


class UtilizationReport(BaseModel):
    rows: list[UtilizationRow]
    summary: UtilizationSummary


class OpeningBalanceRow(BaseModel):
    customer: CustomerRef
    branch_name: str
    amount: Decimal
    effective_date: date
    reference: str
    status: str
    entered_by_name: str
    decided_by_name: str | None


class StatusCount(BaseModel):
    count: int
    amount: Decimal


class OpeningBalancesReport(BaseModel):
    rows: list[OpeningBalanceRow]
    summary: dict[str, StatusCount]  # pending / approved / rejected / cancelled


class ReconciliationReportSummary(BaseModel):
    by_status: dict[str, int]
    by_code: dict[str, int]
    money_open: int
    last_run: "RunOut | None"


class ReconciliationReport(BaseModel):
    """Reconciliation exceptions (brief §29 item 8): the current state, no period."""
    rows: list["ExceptionOut"]
    summary: ReconciliationReportSummary


from app.schemas.reconciliation import ExceptionOut, RunOut  # noqa: E402  (after the models it may import)

ReconciliationReportSummary.model_rebuild()
ReconciliationReport.model_rebuild()
