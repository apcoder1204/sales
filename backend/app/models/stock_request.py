import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, Enum as SAEnum, Text, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class StockRequest(Base):
    __tablename__ = "stock_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    from_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    to_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "approved", "rejected", "fulfilled", name="request_status_enum"),
        nullable=False, default="pending"
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by], lazy="selectin")
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by], lazy="selectin")
    from_branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[from_branch_id], lazy="selectin")
    to_branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[to_branch_id], lazy="selectin")
    items: Mapped[list["StockRequestItem"]] = relationship(
        "StockRequestItem", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("from_branch_id != to_branch_id", name="chk_stock_req_diff_branches"),
    )
