import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class DailyClosingExpense(Base):
    """A 'matumizi' (expense/adjustment) line item a cashier records at closing
    time to explain a cash variance — e.g. cash paid out of the drawer for a
    business expense during the day, or a note explaining a surplus."""
    __tablename__ = "daily_closing_expenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    closing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("daily_closings.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_daily_closing_expense_amount_pos"),
    )
