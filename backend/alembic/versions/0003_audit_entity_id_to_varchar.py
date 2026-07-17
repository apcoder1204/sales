"""change audit_logs.entity_id from UUID to VARCHAR to support non-UUID IDs

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'audit_logs', 'entity_id',
        existing_type=UUID(as_uuid=True),
        type_=sa.String(100),
        existing_nullable=True,
        postgresql_using='entity_id::text',
    )


def downgrade() -> None:
    op.alter_column(
        'audit_logs', 'entity_id',
        existing_type=sa.String(100),
        type_=UUID(as_uuid=True),
        existing_nullable=True,
        postgresql_using='entity_id::uuid',
    )
