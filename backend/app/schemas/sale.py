from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class SaleItemInput(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class SaleCreate(BaseModel):
    branch_id: UUID
    payment_method: Literal["cash", "mobile_money", "bank_transfer"]
    payment_reference: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=500)
    items: list[SaleItemInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_payment_reference(self):
        if self.payment_method in ("mobile_money", "bank_transfer"):
            if not self.payment_reference:
                raise ValueError("Nambari ya kumbukumbu inahitajika kwa Pesa ya Simu na Benki")
        return self


class SaleItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product: str
    quantity: int
    unit_price: Decimal
    cost_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SaleResponse(BaseModel):
    id: UUID
    transaction_no: str
    branch: str
    branch_id: UUID
    cashier: str
    cashier_id: UUID
    subtotal: Decimal
    total_amount: Decimal
    payment_method: str
    payment_reference: str | None
    status: str
    items: list[SaleItemResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptData(BaseModel):
    transaction_no: str
    branch_name: str
    cashier_name: str
    date: str
    items: list[SaleItemResponse]
    subtotal: str
    total_amount: str
    payment_method: str
    payment_reference: str | None


class SaleVoidRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class SaleCreateResponse(BaseModel):
    sale: SaleResponse
    receipt: ReceiptData
