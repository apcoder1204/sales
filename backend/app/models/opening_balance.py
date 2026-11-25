import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Text, CheckConstraint, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class OpeningBalance(Base):
    """An old debt from before the system (decision D5). Entered by one
    admin, approved or rejected by a different one; only an approved row
    is owed (ledger debit + allocatable receivable)."""
    __tablename__ = "opening_balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending", server_default="pending")
    entered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    customer: Mapped["Customer"] = relationship("Customer", lazy="selectin")
    branch: Mapped["Branch"] = relationship("Branch", lazy="selectin")
    enterer: Mapped["User"] = relationship("User", foreign_keys=[entered_by], lazy="selectin")
    decider: Mapped["User | None"] = relationship("User", foreign_keys=[decided_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_opening_balances_amount_pos"),
        CheckConstraint(
            "status IN ('pending','approved','rejected')", name="chk_opening_balances_status"
        ),
        CheckConstraint(
            "decided_by IS NULL OR decided_by <> entered_by", name="chk_opening_balances_two_person"
        ),
    )
