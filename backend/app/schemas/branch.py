from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=1, max_length=20)
    branch_type: Literal["main_store", "pos_point"] = "pos_point"
    address: str | None = Field(None, max_length=2000)
    phone: str | None = Field(None, max_length=30)

    @field_validator("name", "code")
    @classmethod
    def _strip_and_require_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise PydanticCustomError("branch_field_blank", "Sehemu hii haiwezi kuwa tupu")
        return v

    @field_validator("code")
    @classmethod
    def _code_no_spaces(cls, v: str) -> str:
        # Used as a short, stable identifier (receipts, dropdowns, exports)
        # — free-text spaces defeat that purpose and invite copy/paste
        # duplicates that only differ by whitespace.
        if " " in v:
            raise PydanticCustomError("branch_code_has_spaces", "Msimbo wa tawi hauwezi kuwa na nafasi")
        return v.upper()


class BranchUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    code: str | None = Field(None, min_length=1, max_length=20)
    branch_type: Literal["main_store", "pos_point"] | None = None
    address: str | None = Field(None, max_length=2000)
    phone: str | None = Field(None, max_length=30)
    is_active: bool | None = None

    @field_validator("name", "code")
    @classmethod
    def _strip_and_require_content(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise PydanticCustomError("branch_field_blank", "Sehemu hii haiwezi kuwa tupu")
        return v

    @field_validator("code")
    @classmethod
    def _code_no_spaces(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if " " in v:
            raise PydanticCustomError("branch_code_has_spaces", "Msimbo wa tawi hauwezi kuwa na nafasi")
        return v.upper()


class BranchResponse(BaseModel):
    id: UUID
    name: str
    code: str
    branch_type: str
    address: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
