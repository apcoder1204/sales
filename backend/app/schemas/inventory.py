from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class StockAdjustRequest(BaseModel):
    product_id: UUID
    branch_id: UUID
    quantity: int = Field(gt=0)
    type: Literal["stock_in", "stock_out", "adjustment", "damaged"]
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _reason_required_for_writeoffs(self):
        # stock_in (receiving) is routine and self-explanatory. Anything that
        # removes or overrides stock outside the normal sale/transfer flow —
        # stock_out, damaged, adjustment — is exactly what an audit trail
        # needs explained, so it can't be submitted with no reason at all.
        if self.type in ("stock_out", "damaged", "adjustment") and not (self.notes and self.notes.strip()):
            raise ValueError("Sababu inahitajika kwa aina hii ya marekebisho")
        return self


class InventoryMovementResponse(BaseModel):
    id: UUID
    product: str
    product_code: str
    branch: str
    transaction_type: str
    quantity_before: int
    quantity_change: int
    quantity_after: int
    reference_type: str | None
    notes: str | None
    performed_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceBranch(BaseModel):
    branch_id: UUID
    branch_name: str
    branch_code: str
    available_qty: int


class AvailableSourcesResponse(BaseModel):
    main_store_sufficient: bool
    main_store_stock: int
    sources: list[SourceBranch]


class InventoryValuationResponse(BaseModel):
    branch_id: UUID
    branch_name: str
    total_quantity: int
    total_value: str
    product_count: int
