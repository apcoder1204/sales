import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Numeric, ForeignKey, Text, CheckConstraint, Date, DateTime, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class CustomerLedgerEntry(Base):
    """Append-only customer ledger. debit increases what the customer owes,
    credit decreases it. A DB trigger (trg_ledger_append_only) rejects
    UPDATE/DELETE unless `SET LOCAL dukani.ledger_maintenance = 'on'`."""
    __tablename__ = "customer_ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reverses_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_ledger_entries.id")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('sale','payment','payment_reversal','sale_void','opening_balance','opening_void')",
            name="chk_ledger_entry_type",
        ),
        CheckConstraint(
            "debit >= 0 AND credit >= 0 AND (debit > 0) <> (credit > 0)",
            name="chk_ledger_one_side",
        ),
        UniqueConstraint("source_type", "source_id", "entry_type", name="uq_ledger_source_entry"),
        Index("ix_ledger_customer_branch", "customer_id", "branch_id"),
    )
