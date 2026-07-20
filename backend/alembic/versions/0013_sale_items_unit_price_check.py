"""add missing chk_sale_items_unit_price_pos check constraint

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-20
"""
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "chk_sale_items_unit_price_pos", "sale_items", "unit_price >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("chk_sale_items_unit_price_pos", "sale_items", type_="check")
