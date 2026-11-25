from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from app.schemas.customer import CustomerRef


class SaleItemInput(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


PaymentMethod = Literal["cash", "mobile_money", "bank_transfer"]


def _require_reference(method: str, reference: str | None) -> None:
    if method in ("mobile_money", "bank_transfer") and not (reference or "").strip():
        raise PydanticCustomError(
            "payment_reference_required",
            "Nambari ya kumbukumbu inahitajika kwa Pesa ya Simu na Benki",
        )


class PaymentLineInput(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reference: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_reference(self):
        _require_reference(self.method, self.reference)
        return self


class SaleCreate(BaseModel):
    """`payments` (0-3 lines) + optional `customer_id` is the current shape.
    The pre-debt shape `{payment_method, payment_reference}` (browsers still
    holding the old JS bundle) is accepted as "legacy mode": one payment of
    the full total, resolved by the service. Sending both shapes is a 422."""
    branch_id: UUID
    customer_id: UUID | None = None
    payments: list[PaymentLineInput] | None = Field(None, max_length=3)
    payment_method: PaymentMethod | None = None
    payment_reference: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=500)
    items: list[SaleItemInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_payment_shape(self):
        if self.payments is not None and self.payment_method is not None:
            raise PydanticCustomError(
                "payment_shape_conflict", "Tuma `payments` au `payment_method`, si vyote viwili"
            )
        if self.payment_method is not None:
            _require_reference(self.payment_method, self.payment_reference)
        elif self.payments is None:
            self.payments = []
        return self

    @property
    def is_legacy(self) -> bool:
        return self.payments is None


class SaleItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product: str
    quantity: int
    unit_price: Decimal
    cost_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SalePaymentOut(BaseModel):
    """A payment applied to a sale; `amount` is the part applied to this sale."""
    id: UUID
    payment_no: str
    kind: str
    method: str
    amount: Decimal
    reference: str | None
    status: str
    created_at: datetime


class SaleResponse(BaseModel):
    id: UUID
    transaction_no: str
    branch: str
    branch_id: UUID
    cashier: str
    cashier_id: UUID
    subtotal: Decimal
    total_amount: Decimal
    # The single sale-time payment's method, "mixed" for several, "credit"
    # for none.
    payment_method: str | None
    payment_reference: str | None
    status: str
    items: list[SaleItemResponse]
    created_at: datetime
    voided_by: str | None = None
    voided_at: datetime | None = None
    void_reason: str | None = None
    customer: CustomerRef | None = None
    payments: list[SalePaymentOut] = []
    paid: Decimal = Decimal("0.00")
    outstanding: Decimal = Decimal("0.00")
    payment_status: str = "PAID"
    due_date: date | None = None

    model_config = {"from_attributes": True}


class ReceiptPaymentLine(BaseModel):
    method: str
    amount: str
    reference: str | None = None


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
    customer_name: str | None = None
    payments: list[ReceiptPaymentLine] = []
    paid: str | None = None
    balance: str | None = None
    due_date: str | None = None


class SaleVoidRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class SaleCreateResponse(BaseModel):
    sale: SaleResponse
    receipt: ReceiptData
