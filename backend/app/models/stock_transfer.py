import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, Enum as SAEnum, Text, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_requests.id"))
    from_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    to_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    transferred_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("completed", "cancelled", name="transfer_status_enum"),
        nullable=False, default="completed"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()

    from_branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[from_branch_id], lazy="selectin")
    to_branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[to_branch_id], lazy="selectin")
    executor: Mapped["User"] = relationship("User", foreign_keys=[transferred_by], lazy="selectin")
    items: Mapped[list["StockTransferItem"]] = relationship(
        "StockTransferItem", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("from_branch_id != to_branch_id", name="chk_stock_tf_diff_branches"),
    )
