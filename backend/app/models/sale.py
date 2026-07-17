import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Enum as SAEnum, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    cashier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(
        SAEnum("cash", "mobile_money", "bank_transfer", name="payment_method_enum"),
        nullable=False
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        SAEnum("completed", "voided", name="sale_status_enum"),
        nullable=False, default="completed"
    )
    voided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    voided_at: Mapped[datetime | None] = mapped_column()
    void_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    items: Mapped[list["SaleItem"]] = relationship(
        "SaleItem", cascade="all, delete-orphan", lazy="selectin"
    )
    branch: Mapped["Branch"] = relationship("Branch", lazy="selectin")
    cashier: Mapped["User"] = relationship("User", foreign_keys=[cashier_id], lazy="selectin")
    voider: Mapped["User | None"] = relationship("User", foreign_keys=[voided_by], lazy="noload")

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="chk_sales_subtotal_pos"),
        CheckConstraint("total_amount > 0", name="chk_sales_total_pos"),
    )
