from uuid import UUID
from datetime import datetime, date
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    username: str
    user_role: str
    branch: str | None
    action: str
    category: str
    entity_type: str | None
    entity_id: UUID | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogFilter(BaseModel):
    category: str | None = None
    user_id: UUID | None = None
    action: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    page: int = 1
    per_page: int = 50
