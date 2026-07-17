"""add daily_closing_expenses (matumizi) for cash-variance reconciliation

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("daily_closing_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("closing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("daily_closings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("amount > 0", name="chk_daily_closing_expense_amount_pos"),
    )
    op.create_index("idx_daily_closing_expenses_closing_id", "daily_closing_expenses", ["closing_id"])


def downgrade() -> None:
    op.drop_index("idx_daily_closing_expenses_closing_id", table_name="daily_closing_expenses")
    op.drop_table("daily_closing_expenses")
