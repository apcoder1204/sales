from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ProductCreate(BaseModel):
    product_code: str | None = Field(None, max_length=30)
    name: str = Field(min_length=2, max_length=200)
    category_id: int
    brand: str | None = None
    family_name: str | None = None
    family_id: str | None = None
    unit: str = "Kipande"
    description: str | None = None
    cost_price: Decimal = Field(ge=0)
    selling_price: Decimal = Field(ge=0)
    minimum_stock: int = Field(ge=0, default=5)

    @model_validator(mode="after")
    def selling_gte_cost(self):
        if self.selling_price < self.cost_price:
            raise ValueError("Bei ya uuzaji lazima iwe kubwa au sawa na gharama")
        return self


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: int | None = None
    brand: str | None = None
    family_name: str | None = None
    family_id: str | None = None
    unit: str | None = None
    description: str | None = None
    cost_price: Decimal | None = Field(None, ge=0)
    selling_price: Decimal | None = Field(None, ge=0)
    minimum_stock: int | None = Field(None, ge=0)
    status: Literal["active", "inactive", "discontinued"] | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    name_sw: str | None = None
    category_code: str | None = Field(None, max_length=30)
    brand_name: str | None = None
    family: str | None = None
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    name_sw: str | None = None
    category_code: str | None = None
    brand_name: str | None = None
    family: str | None = None
    description: str | None = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    name_sw: str | None
    category_code: str | None = None
    brand_name: str | None = None
    family: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class BranchStock(BaseModel):
    branch_id: UUID
    branch_name: str
    branch_code: str
    branch_type: str = 'pos_point'
    quantity: int
    reserved_qty: int
    available_qty: int
    is_low_stock: bool


class ProductResponse(BaseModel):
    id: UUID
    product_code: str
    name: str
    category: str
    category_id: int
    brand: str | None
    family_name: str | None
    unit: str = "Kipande"
    description: str | None = None
    cost_price: Decimal
    selling_price: Decimal
    minimum_stock: int
    status: str
    created_at: datetime
    available_qty: int | None = None
    is_low_stock: bool | None = None

    model_config = {"from_attributes": True}


class ProductWithInventory(ProductResponse):
    inventory: list[BranchStock] = []
