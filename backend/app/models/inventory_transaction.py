import uuid
from datetime import datetime
from sqlalchemy import Integer, ForeignKey, Enum as SAEnum, Text, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        SAEnum("stock_in", "stock_out", "sale", "transfer_out", "transfer_in",
               "adjustment", "damaged", name="inv_transaction_type_enum"),
        nullable=False
    )
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reference_type: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    performed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    product: Mapped["Product"] = relationship("Product", lazy="selectin")
    branch: Mapped["Branch"] = relationship("Branch", lazy="selectin")
    performer: Mapped["User"] = relationship("User", foreign_keys=[performed_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("quantity_after >= 0", name="chk_inv_tx_qty_after_non_neg"),
        CheckConstraint("quantity_after = quantity_before + quantity_change", name="chk_inv_tx_math"),
    )
