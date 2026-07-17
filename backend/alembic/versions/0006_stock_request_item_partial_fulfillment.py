"""stock request items: support partial approval/fulfillment per line item

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stock_request_items", sa.Column("approved_qty", sa.Integer, nullable=True))
    op.add_column("stock_request_items", sa.Column(
        "status",
        postgresql.ENUM("pending", "approved", "rejected", "fulfilled", name="request_status_enum", create_type=False),
        nullable=False, server_default="pending",
    ))
    op.add_column("stock_request_items", sa.Column("review_notes", sa.Text, nullable=True))
    op.add_column("stock_request_items", sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_check_constraint(
        "chk_stock_req_items_approved_qty",
        "stock_request_items",
        "approved_qty IS NULL OR (approved_qty >= 0 AND approved_qty <= requested_qty)",
    )


def downgrade() -> None:
    op.drop_constraint("chk_stock_req_items_approved_qty", "stock_request_items", type_='check')
    op.drop_column("stock_request_items", "reviewed_at")
    op.drop_column("stock_request_items", "review_notes")
    op.drop_column("stock_request_items", "status")
    op.drop_column("stock_request_items", "approved_qty")
