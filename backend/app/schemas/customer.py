from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.exceptions import ValidationException
from app.core.phone import normalize_phone

CustomerType = Literal["individual", "business", "institution", "government"]


def _phone(v: str | None) -> str | None:
    if v is None:
        return v
    try:
        return normalize_phone(v)
    except ValidationException:
        raise ValueError("Namba ya simu si sahihi")


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    phone: str
    email: str | None = Field(None, max_length=150)
    address: str | None = Field(None, max_length=255)
    customer_type: CustomerType = "individual"
    tin: str | None = Field(None, max_length=30)
    notes: str | None = Field(None, max_length=500)

    @field_validator("phone")
    @classmethod
    def _norm_phone(cls, v):
        return _phone(v)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Jina ni fupi mno")
        return v


class CustomerUpdate(BaseModel):
    """Profile fields only — credit terms and status go through
    CustomerCreditUpdate (admin only); unknown keys are ignored."""
    name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = None
    email: str | None = Field(None, max_length=150)
    address: str | None = Field(None, max_length=255)
    customer_type: CustomerType | None = None
    tin: str | None = Field(None, max_length=30)
    notes: str | None = Field(None, max_length=500)

    @field_validator("phone")
    @classmethod
    def _norm_phone(cls, v):
        return _phone(v)


class CustomerCreditUpdate(BaseModel):
    credit_limit: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    credit_days: int = Field(ge=0, le=365)
    status: Literal["active", "inactive"]
    reason: str = Field(min_length=5, max_length=500)


class CustomerResponse(BaseModel):
    id: UUID
    customer_no: str
    name: str
    phone: str
    email: str | None
    address: str | None
    customer_type: str
    tin: str | None
    credit_limit: Decimal
    credit_days: int
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerSummary(BaseModel):
    balance: Decimal = Decimal("0.00")
    overdue: Decimal = Decimal("0.00")
    available_credit: Decimal = Decimal("0.00")
    last_payment_at: datetime | None = None


class CustomerDetailResponse(BaseModel):
    customer: CustomerResponse
    summary: CustomerSummary


class CustomerRef(BaseModel):
    id: UUID
    customer_no: str
    name: str
    phone: str

    model_config = {"from_attributes": True}


class CustomerListItem(CustomerResponse):
    """List row: profile plus the summary figures (scoped like the detail)."""
    balance: Decimal = Decimal("0.00")
    overdue: Decimal = Decimal("0.00")
    available_credit: Decimal = Decimal("0.00")
    last_payment_at: datetime | None = None
