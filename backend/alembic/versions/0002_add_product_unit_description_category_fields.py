"""add unit+description to products, category_code+family to categories

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('products', sa.Column('unit', sa.String(50), nullable=False, server_default='Kipande'))
    op.add_column('products', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('categories', sa.Column('category_code', sa.String(30), nullable=True))
    op.add_column('categories', sa.Column('family', sa.String(100), nullable=True))
    op.create_unique_constraint('uq_categories_category_code', 'categories', ['category_code'])


def downgrade() -> None:
    op.drop_constraint('uq_categories_category_code', 'categories', type_='unique')
    op.drop_column('categories', 'family')
    op.drop_column('categories', 'category_code')
    op.drop_column('products', 'description')
    op.drop_column('products', 'unit')
