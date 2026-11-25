from pydantic import BaseModel, Field


class WhatsAppSettingsResponse(BaseModel):
    number: str | None
    locked: bool
    enabled: bool
    connected: bool


class WhatsAppSettingsUpdate(BaseModel):
    number: str = Field(..., max_length=32)
