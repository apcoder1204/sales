"""allow product_code and category_code to repeat across rows

Both codes are business/supplier batch labels, not lookup keys (nothing in
the app queries by them) — the unique constraints only got in the way of
recording multiple products/categories that share a supplier code.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-17
"""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("products_product_code_key", "products", type_='unique')
    op.drop_constraint("uq_categories_category_code", "categories", type_='unique')


def downgrade() -> None:
    op.create_unique_constraint("uq_categories_category_code", "categories", ["category_code"])
    op.create_unique_constraint("products_product_code_key", "products", ["product_code"])
