import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, ForeignKey, Text, CheckConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class Customer(Base):
    """A customer registered once and shared by every branch (decision D1).
    Debts are per branch (ledger/receivables); the credit limit is one total
    across all branches (D4). Never deleted, only deactivated."""
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(String(255))
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    tin: Mapped[str | None] = mapped_column(String(30))
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    credit_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active", server_default="active")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "customer_type IN ('individual','business','institution','government')",
            name="chk_customers_type",
        ),
        CheckConstraint("status IN ('active','inactive')", name="chk_customers_status"),
        CheckConstraint("credit_limit >= 0", name="chk_customers_credit_limit"),
        CheckConstraint("credit_days BETWEEN 0 AND 365", name="chk_customers_credit_days"),
    )
