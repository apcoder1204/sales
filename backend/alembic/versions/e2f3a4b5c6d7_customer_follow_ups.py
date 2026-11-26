"""customer follow-up notes (debt collection, stage 2)

New table only; no existing rows change.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-27 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("contact_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("expected_payment_date", sa.Date(), nullable=True),
        sa.Column("responsible_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("method IN ('phone','visit','sms','whatsapp')", name="chk_follow_ups_method"),
    )
    op.create_index("ix_follow_ups_customer_date", "customer_follow_ups", ["customer_id", "contact_date"])


def downgrade() -> None:
    op.drop_index("ix_follow_ups_customer_date", table_name="customer_follow_ups")
    op.drop_table("customer_follow_ups")
