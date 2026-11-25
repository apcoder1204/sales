import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Numeric, ForeignKey, Text, CheckConstraint, Date, DateTime, UniqueConstraint, Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class Payment(Base):
    """Every shilling received: at the till (kind='sale') or against debt
    (kind='debt'). Never deleted; a mistake is reversed (status='reversed')."""
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    method: Mapped[str] = mapped_column(
        SAEnum("cash", "mobile_money", "bank_transfer", name="payment_method_enum", create_type=False),
        nullable=False,
    )
    reference: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active", server_default="active")
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_reason: Mapped[str | None] = mapped_column(Text)
    # Receipt snapshot for debt payments (the branch balance before/after).
    # Informational only — balances are always computed from the ledger.
    balance_before: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        "PaymentAllocation", lazy="selectin", back_populates="payment"
    )
    customer: Mapped["Customer | None"] = relationship("Customer", lazy="selectin")
    branch: Mapped["Branch"] = relationship("Branch", lazy="selectin")
    receiver: Mapped["User"] = relationship("User", foreign_keys=[received_by], lazy="selectin")
    reverser: Mapped["User | None"] = relationship("User", foreign_keys=[reversed_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("kind IN ('sale','debt')", name="chk_payments_kind"),
        CheckConstraint("status IN ('active','reversed')", name="chk_payments_status"),
        CheckConstraint("amount > 0", name="chk_payments_amount_pos"),
        CheckConstraint("kind <> 'debt' OR customer_id IS NOT NULL", name="chk_payments_debt_customer"),
        Index("ix_payments_branch_created", "branch_id", "created_at"),
        Index("ix_payments_customer", "customer_id"),
    )


class PaymentAllocation(Base):
    """Which receivable (a sale or an approved old debt) a payment settles.
    Never deleted; active iff its payment is active."""
    __tablename__ = "payment_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales.id"))
    opening_balance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opening_balances.id")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    payment: Mapped["Payment"] = relationship("Payment", back_populates="allocations")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_allocations_amount_pos"),
        CheckConstraint(
            "(sale_id IS NULL) <> (opening_balance_id IS NULL)", name="chk_allocations_one_target"
        ),
        UniqueConstraint("payment_id", "sale_id", name="uq_allocations_payment_sale"),
        UniqueConstraint("payment_id", "opening_balance_id", name="uq_allocations_payment_ob"),
        Index("ix_allocations_sale", "sale_id"),
        Index("ix_allocations_opening_balance", "opening_balance_id"),
    )
