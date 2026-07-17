"""sales: remove VAT — subtotal now equals grand total

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: the model previously declared a "chk_sales_vat_pos" CheckConstraint,
    # but the 0001 baseline migration never actually created it in the DB —
    # nothing to drop here besides the columns themselves.
    op.drop_column("sales", "vat_amount")
    op.drop_column("sales", "vat_rate")


def downgrade() -> None:
    op.add_column("sales", sa.Column("vat_rate", sa.Numeric(6, 4), nullable=False, server_default="0.1800"))
    op.add_column("sales", sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False, server_default="0"))
