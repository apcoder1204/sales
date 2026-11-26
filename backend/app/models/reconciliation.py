import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Integer, Numeric, ForeignKey, Text, CheckConstraint, Date, DateTime, Index, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

RUN_SCOPES = ("all", "branch", "customer", "sale", "payment")
RUN_STATUSES = ("PASSED", "WARNING", "FAILED")
EXCEPTION_STATUSES = ("OPEN", "UNDER_REVIEW", "RESOLVED", "DISMISSED")
LIVE_STATUSES = ("OPEN", "UNDER_REVIEW")


class ReconciliationRun(Base):
    """One on-demand reconciliation (brief §20). Records what was checked
    and what was found; a run never writes financial rows."""
    __tablename__ = "reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    sale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales.id"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"))
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    records_examined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discrepancy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    runner: Mapped["User"] = relationship("User", foreign_keys=[run_by], lazy="selectin")
    branch: Mapped["Branch | None"] = relationship("Branch", lazy="selectin")
    customer: Mapped["Customer | None"] = relationship("Customer", lazy="selectin")
    sale: Mapped["Sale | None"] = relationship("Sale", lazy="selectin")
    payment: Mapped["Payment | None"] = relationship("Payment", lazy="selectin")

    __table_args__ = (
        CheckConstraint("scope IN ('all','branch','customer','sale','payment')", name="chk_recon_runs_scope"),
        CheckConstraint("status IN ('PASSED','WARNING','FAILED')", name="chk_recon_runs_status"),
        Index("ix_recon_runs_created", "created_at"),
    )


class ReconciliationException(Base):
    """A discrepancy found by a run (brief §21). One live (OPEN or
    UNDER_REVIEW) row per fingerprint; repeat runs update it. Its status is
    changed by a person, with a reason; the fix itself is always a normal
    correcting action, never an edit made here."""
    __tablename__ = "reconciliation_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_group: Mapped[str] = mapped_column(String(1), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="OPEN", server_default="OPEN")
    first_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reconciliation_runs.id"), nullable=False)
    last_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reconciliation_runs.id"), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    sale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales.id"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"))
    opening_balance_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("opening_balances.id"))
    closing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("daily_closings.id"))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    expected: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    actual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(Text)
    status_reference: Mapped[str | None] = mapped_column(String(100))
    status_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    first_run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", foreign_keys=[first_run_id], lazy="selectin")
    last_run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", foreign_keys=[last_run_id], lazy="selectin")
    customer: Mapped["Customer | None"] = relationship("Customer", lazy="selectin")
    sale: Mapped["Sale | None"] = relationship("Sale", lazy="selectin")
    payment: Mapped["Payment | None"] = relationship("Payment", lazy="selectin")
    opening_balance: Mapped["OpeningBalance | None"] = relationship("OpeningBalance", lazy="selectin")
    closing: Mapped["DailyClosing | None"] = relationship("DailyClosing", lazy="selectin")
    branch: Mapped["Branch | None"] = relationship("Branch", lazy="selectin")
    changer: Mapped["User | None"] = relationship("User", foreign_keys=[status_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("check_group IN ('A','B','C','D','E','F','G')", name="chk_recon_exc_group"),
        CheckConstraint("severity IN ('money','warning')", name="chk_recon_exc_severity"),
        CheckConstraint("status IN ('OPEN','UNDER_REVIEW','RESOLVED','DISMISSED')", name="chk_recon_exc_status"),
        Index("uq_recon_exception_live", "fingerprint", unique=True,
              postgresql_where=text("status IN ('OPEN','UNDER_REVIEW')")),
        Index("ix_recon_exceptions_status", "status", "detected_at"),
    )
