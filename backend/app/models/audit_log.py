import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.sql import func
from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    user_role: Mapped[str] = mapped_column(String(50), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    # Only set for transfer events (request/direct transfer), which move
    # stock between two branches and so need attribution to both, not just
    # the "from"/acting branch in branch_id — a branch-scoped audit view
    # (e.g. general_manager's transfers-only view) must see a transfer
    # regardless of which side of it that branch was on.
    to_branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(
        SAEnum("authentication", "products", "inventory", "sales",
               "transfers", "users", "system", name="audit_category_enum"),
        nullable=False
    )
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
