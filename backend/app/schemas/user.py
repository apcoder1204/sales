from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr | None = None
    password: str = Field(min_length=4)
    role_id: int
    branch_id: UUID | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role_id: int | None = None
    branch_id: UUID | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=4)


class UserResponse(BaseModel):
    id: UUID
    username: str
    full_name: str
    email: str | None
    role: str
    role_id: int
    branch: str | None
    branch_id: UUID | None
    is_active: bool
    last_login: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
