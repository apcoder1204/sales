import uuid
from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Text, CheckConstraint, Date, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base

FOLLOW_UP_METHODS = ("phone", "visit", "sms", "whatsapp")


class CustomerFollowUp(Base):
    """A debt-collection contact note (brief §16). Purely informational: it
    never touches payments, the ledger or any balance."""
    __tablename__ = "customer_follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    contact_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    expected_payment_date: Mapped[date | None] = mapped_column(Date)
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    branch: Mapped["Branch"] = relationship("Branch", lazy="selectin")
    responsible: Mapped["User"] = relationship("User", foreign_keys=[responsible_user_id], lazy="selectin")

    __table_args__ = (
        CheckConstraint("method IN ('phone','visit','sms','whatsapp')", name="chk_follow_ups_method"),
        Index("ix_follow_ups_customer_date", "customer_id", "contact_date"),
    )
