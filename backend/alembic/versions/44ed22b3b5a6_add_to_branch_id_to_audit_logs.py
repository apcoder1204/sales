"""add to_branch_id to audit_logs

Revision ID: 44ed22b3b5a6
Revises: 0014
Create Date: 2026-09-21 07:52:55.410427

"""
from alembic import op
import sqlalchemy as sa

revision = '44ed22b3b5a6'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('to_branch_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_audit_logs_to_branch_id', 'audit_logs', 'branches', ['to_branch_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_audit_logs_to_branch_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'to_branch_id')
