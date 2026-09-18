from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.core.security import validate_password_strength


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, v):
        return validate_password_strength(v)

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Nenosiri na uthibitisho hazifanani")
        return self


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: UUID
    username: str
    full_name: str
    email: str | None = None
    role: str
    branch_id: UUID | None
    branch: str | None

    model_config = {"from_attributes": True}

class UserProfileUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50)
    full_name: str | None = None
    email: EmailStr | None = None
    current_password: str | None = None
    new_password: str | None = Field(None, min_length=8, max_length=72)
    confirm_password: str | None = None

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, v):
        return validate_password_strength(v) if v is not None else v

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.new_password is not None and self.new_password != self.confirm_password:
            raise ValueError("Nenosiri na uthibitisho hazifanani")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserProfile


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
