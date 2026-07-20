from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.core.security import validate_password_strength


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=72)
    confirm_password: str
    role_id: int
    branch_id: UUID | None = None

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v):
        return validate_password_strength(v)

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Nenosiri na uthibitisho hazifanani")
        return self


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role_id: int | None = None
    branch_id: UUID | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=72)
    confirm_password: str | None = None

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v):
        return validate_password_strength(v) if v is not None else v

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password is not None and self.password != self.confirm_password:
            raise ValueError("Nenosiri na uthibitisho hazifanani")
        return self


class RoleResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


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
