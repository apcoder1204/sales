"""add daily_closings table for end-of-day cash closing

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE daily_closing_status_enum AS ENUM ('open', 'closed')")

    op.create_table("daily_closings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("business_date", sa.Date, nullable=False),
        sa.Column("status", postgresql.ENUM("open", "closed", name="daily_closing_status_enum", create_type=False), nullable=False, server_default="open"),
        sa.Column("total_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_mobile_money", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_bank_transfer", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_sales_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_revenue", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("cash_variance", sa.Numeric(14, 2), nullable=True),
        sa.Column("closing_notes", sa.Text, nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reopened_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reopen_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("branch_id", "business_date", name="uq_daily_closing_branch_date"),
    )
    op.create_index("idx_daily_closings_branch_date", "daily_closings", ["branch_id", "business_date"])


def downgrade() -> None:
    op.drop_index("idx_daily_closings_branch_date", table_name="daily_closings")
    op.drop_table("daily_closings")
    op.execute("DROP TYPE daily_closing_status_enum")
