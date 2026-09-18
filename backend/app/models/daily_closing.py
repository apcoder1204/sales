import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Date, Integer, Numeric, ForeignKey, Enum as SAEnum, Text, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class DailyClosing(Base):
    """A single register/operating period for a branch. Most branches have
    exactly one per business_date (register_number=1, the original model)
    — but a branch may open additional registers on the same business_date
    after closing (register_number 2, 3, ...) so sales taken after a
    closing are tracked as their own period rather than silently folded
    into the already-reconciled one. See [[opening_register]] design notes
    in daily_closing_service.py for how period boundaries are computed."""

    __tablename__ = "daily_closings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    register_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        SAEnum("open", "closed", name="daily_closing_status_enum"),
        nullable=False, default="open"
    )
    opened_at: Mapped[datetime | None] = mapped_column()
    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    opening_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_mobile_money: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_bank_transfer: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    cash_variance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    closing_notes: Mapped[str | None] = mapped_column(Text)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column()
    reopened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reopened_at: Mapped[datetime | None] = mapped_column()
    reopen_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[branch_id], lazy="selectin")
    opener: Mapped["User | None"] = relationship("User", foreign_keys=[opened_by], lazy="selectin")
    closer: Mapped["User | None"] = relationship("User", foreign_keys=[closed_by], lazy="selectin")
    reopener: Mapped["User | None"] = relationship("User", foreign_keys=[reopened_by], lazy="selectin")
    expenses: Mapped[list["DailyClosingExpense"]] = relationship(
        "DailyClosingExpense", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "branch_id", "business_date", "register_number",
            name="uq_daily_closing_branch_date_register",
        ),
        # At most one register may be OPEN for a given branch at any time —
        # the DB-level guard against two concurrent "open register" calls
        # racing each other (see DailyClosingService.open_register).
        Index(
            "uq_daily_closing_one_open_per_branch", "branch_id",
            unique=True, postgresql_where=text("status = 'open'"),
        ),
    )
