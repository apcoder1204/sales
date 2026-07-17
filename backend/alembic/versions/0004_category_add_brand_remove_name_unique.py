"""category: add brand_name column, drop unique constraint on name

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('brand_name', sa.String(100), nullable=True))
    op.drop_constraint('categories_name_key', 'categories', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('categories_name_key', 'categories', ['name'])
    op.drop_column('categories', 'brand_name')
