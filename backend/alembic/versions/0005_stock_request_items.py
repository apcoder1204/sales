"""stock requests: support multiple products per request via stock_request_items

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("stock_request_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("requested_qty", sa.Integer, nullable=False),
        sa.Column("main_store_had_stock", sa.Boolean, nullable=False, server_default="true"),
        sa.CheckConstraint("requested_qty > 0", name="chk_stock_req_items_qty_pos"),
    )
    op.create_index("idx_stock_req_items_request_id", "stock_request_items", ["request_id"])

    # Data is disposable (demo/pre-production) — clean cut instead of backfill.
    # Detach any existing transfer records from their (about to be wiped)
    # request rows first, so transfer history itself is left untouched.
    op.execute("UPDATE stock_transfers SET request_id = NULL WHERE request_id IS NOT NULL")
    op.execute("DELETE FROM stock_requests")

    op.drop_constraint("chk_stock_req_qty_pos", "stock_requests", type_='check')
    op.drop_column("stock_requests", "product_id")
    op.drop_column("stock_requests", "quantity")
    op.drop_column("stock_requests", "main_store_had_stock")


def downgrade() -> None:
    op.add_column("stock_requests", sa.Column("main_store_had_stock", sa.Boolean, nullable=False, server_default="true"))
    op.add_column("stock_requests", sa.Column("quantity", sa.Integer, nullable=False, server_default="1"))
    op.add_column("stock_requests", sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True))
    op.create_check_constraint("chk_stock_req_qty_pos", "stock_requests", "quantity > 0")
    op.drop_index("idx_stock_req_items_request_id", table_name="stock_request_items")
    op.drop_table("stock_request_items")
