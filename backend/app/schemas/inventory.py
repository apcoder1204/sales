from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class StockAdjustRequest(BaseModel):
    product_id: UUID
    branch_id: UUID
    quantity: int = Field(gt=0)
    type: Literal["stock_in", "stock_out", "adjustment", "damaged"]
    notes: str | None = None


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
