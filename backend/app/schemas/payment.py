from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError

from app.schemas.customer import CustomerRef
from app.schemas.sale import PaymentMethod, _require_reference


class AllocationInput(BaseModel):
    sale_id: UUID | None = None
    opening_balance_id: UUID | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.sale_id is None) == (self.opening_balance_id is None):
            raise PydanticCustomError(
                "allocation_target", "Chagua muamala mmoja au deni moja la zamani"
            )
        return self


class DebtPaymentCreate(BaseModel):
    branch_id: UUID | None = None
    method: PaymentMethod
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reference: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=500)
    allocations: list[AllocationInput] | None = Field(None, max_length=50)

    @model_validator(mode="after")
    def validate_reference(self):
        _require_reference(self.method, self.reference)
        return self


class PaymentReverseRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ReceivableOut(BaseModel):
    kind: Literal["sale", "opening_balance"]
    id: UUID
    reference: str
    branch_id: UUID
    branch_name: str
    date: date
    due_date: date | None
    amount: Decimal
    paid: Decimal
    outstanding: Decimal
    status: str

    model_config = {"from_attributes": True}


class AllocationOut(BaseModel):
    receivable_kind: Literal["sale", "opening_balance"]
    receivable_id: UUID
    reference: str
    amount: Decimal


class PaymentOut(BaseModel):
    id: UUID
    payment_no: str
    kind: str
    customer: CustomerRef | None
    branch_id: UUID
    branch_name: str
    method: str
    reference: str | None
    amount: Decimal
    business_date: date
    received_by_name: str
    notes: str | None
    status: str
    reversed_by_name: str | None
    reversed_at: datetime | None
    reversal_reason: str | None
    allocations: list[AllocationOut]
    created_at: datetime


class ReceiptAllocationLine(BaseModel):
    reference: str
    amount: str


class PaymentReceipt(BaseModel):
    business_name: str
    payment_no: str
    customer_name: str
    customer_no: str
    date: str
    amount: str
    method: str
    reference: str | None
    allocations: list[ReceiptAllocationLine]
    balance_before: str | None
    balance_after: str | None
    branch_name: str
    received_by: str
    reversed: bool
