"""add opening-register fields and multi-period support to daily_closings

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_closings",
        sa.Column("register_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "daily_closings", sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "daily_closings",
        sa.Column("opened_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_daily_closings_opened_by_users", "daily_closings", "users",
        ["opened_by"], ["id"],
    )
    op.add_column(
        "daily_closings", sa.Column("opening_cash", sa.Numeric(14, 2), nullable=True)
    )

    op.drop_constraint("uq_daily_closing_branch_date", "daily_closings", type_="unique")
    op.create_unique_constraint(
        "uq_daily_closing_branch_date_register",
        "daily_closings",
        ["branch_id", "business_date", "register_number"],
    )

    # At most one OPEN register per branch at any time — enforced at the DB
    # level so two concurrent "open register" requests can't both succeed.
    op.execute(
        "CREATE UNIQUE INDEX uq_daily_closing_one_open_per_branch "
        "ON daily_closings (branch_id) WHERE status = 'open'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_daily_closing_one_open_per_branch")
    op.drop_constraint(
        "uq_daily_closing_branch_date_register", "daily_closings", type_="unique"
    )
    op.create_unique_constraint(
        "uq_daily_closing_branch_date", "daily_closings", ["branch_id", "business_date"]
    )
    op.drop_constraint(
        "fk_daily_closings_opened_by_users", "daily_closings", type_="foreignkey"
    )
    op.drop_column("daily_closings", "opening_cash")
    op.drop_column("daily_closings", "opened_by")
    op.drop_column("daily_closings", "opened_at")
    op.drop_column("daily_closings", "register_number")
