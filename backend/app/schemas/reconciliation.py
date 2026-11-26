from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.customer import CustomerRef

Period = Literal["today", "yesterday", "week", "month", "last_month", "custom"]


class RunCreate(BaseModel):
    scope: Literal["all", "branch", "customer", "sale", "payment"]
    branch_id: UUID | None = None
    customer_id: UUID | None = None
    sale_id: UUID | None = None
    payment_id: UUID | None = None
    period: Period = "month"
    from_date: date | None = None
    to_date: date | None = None


class ClosingRef(BaseModel):
    business_date: date
    register_number: int


class ExceptionOut(BaseModel):
    id: UUID
    group: str
    code: str
    severity: str
    status: str
    customer: CustomerRef | None
    sale_id: UUID | None
    sale_no: str | None
    payment_id: UUID | None
    payment_no: str | None
    opening_balance_ref: str | None
    closing: ClosingRef | None
    branch_id: UUID | None
    branch_name: str | None
    expected: Decimal | None
    actual: Decimal | None
    difference: Decimal | None
    detail: str
    detected_at: datetime
    last_seen_at: datetime
    first_run_no: str
    last_run_no: str
    status_reason: str | None
    status_reference: str | None
    status_by_name: str | None
    status_at: datetime | None


class RunOut(BaseModel):
    id: UUID
    run_no: str
    scope: str
    branch_id: UUID | None
    branch_name: str | None
    customer: CustomerRef | None
    sale_no: str | None
    payment_no: str | None
    date_from: date
    date_to: date
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    run_by_name: str
    records_examined: int
    discrepancy_count: int
    warning_count: int
    suppressed_count: int
    status: str
    by_code: dict[str, int]
    summary: dict


class RunDetailOut(RunOut):
    exceptions: list[ExceptionOut]


class StatusChange(BaseModel):
    status: Literal["OPEN", "UNDER_REVIEW", "RESOLVED", "DISMISSED"]
    reason: str = Field(min_length=5, max_length=500)
    reference: str | None = Field(None, max_length=100)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip_reason(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("reference", mode="before")
    @classmethod
    def _strip_reference(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v
