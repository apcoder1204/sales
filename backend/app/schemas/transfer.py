from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class StockRequestItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class StockRequestCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    from_branch_id: UUID
    to_branch_id: UUID
    items: list[StockRequestItemCreate] = Field(min_length=1, max_length=100)


class StockRequestReview(BaseModel):
    notes: str | None = Field(None, max_length=500)


class StockRequestItemApproval(BaseModel):
    item_id: UUID
    approved_qty: int = Field(ge=0)


class StockRequestApprovalRequest(BaseModel):
    items: list[StockRequestItemApproval] = Field(min_length=1, max_length=100)
    notes: str | None = Field(None, max_length=500)


class DirectTransferItem(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class DirectTransferCreate(BaseModel):
    from_branch_id: UUID
    to_branch_id: UUID
    notes: str | None = Field(None, max_length=500)
    items: list[DirectTransferItem] = Field(min_length=1, max_length=100)


class StockRequestItemResponse(BaseModel):
    id: UUID
    product: str
    product_code: str
    product_id: UUID
    requested_qty: int
    approved_qty: int | None
    item_status: str
    main_store_had_stock: bool

    model_config = {"from_attributes": True}


class StockRequestResponse(BaseModel):
    id: UUID
    request_no: str
    requested_by: str
    from_branch: str
    from_branch_id: UUID
    to_branch: str
    to_branch_id: UUID
    items: list[StockRequestItemResponse]
    items_count: int
    is_partial: bool
    reason: str | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransferItemResponse(BaseModel):
    product: str
    product_id: UUID
    quantity: int
    unit_cost: Decimal

    model_config = {"from_attributes": True}


class StockTransferResponse(BaseModel):
    id: UUID
    transfer_no: str
    from_branch: str
    from_branch_id: UUID
    to_branch: str
    to_branch_id: UUID
    transferred_by: str
    status: str
    notes: str | None
    items: list[TransferItemResponse]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
