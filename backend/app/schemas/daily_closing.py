from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class ClosingPreviewResponse(BaseModel):
    branch_id: UUID
    branch_name: str
    business_date: date
    already_closed: bool
    total_cash: float
    total_mobile_money: float
    total_bank_transfer: float
    total_sales_count: int
    total_revenue: float


class ExpenseEntry(BaseModel):
    description: str = Field(min_length=2, max_length=500)
    amount: Decimal = Field(gt=0)


class ExpenseResponse(BaseModel):
    id: UUID
    description: str
    amount: Decimal

    model_config = {"from_attributes": True}


class CloseDayRequest(BaseModel):
    branch_id: UUID
    business_date: date | None = None
    counted_cash: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=500)
    expenses: list[ExpenseEntry] = Field(default=[], max_length=100)


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ClosingResponse(BaseModel):
    id: UUID
    branch_id: UUID
    branch_name: str
    business_date: date
    status: str
    total_cash: Decimal
    total_mobile_money: Decimal
    total_bank_transfer: Decimal
    total_sales_count: int
    total_revenue: Decimal
    counted_cash: Decimal | None
    cash_variance: Decimal | None
    total_expenses: Decimal
    expenses: list[ExpenseResponse]
    closing_notes: str | None
    closed_by: str | None
    closed_at: datetime | None
    reopened_by: str | None
    reopened_at: datetime | None
    reopen_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
