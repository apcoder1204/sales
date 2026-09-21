"""add idempotency_keys table

Revision ID: e5c2670d4b7c
Revises: b51cdc9a9c13
Create Date: 2026-09-21 11:36:31.490749

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'e5c2670d4b7c'
down_revision = 'b51cdc9a9c13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "endpoint", "key", name="uq_idempotency_user_endpoint_key"),
    )
    # Retrieval is always by the same (user_id, endpoint, key) triple the
    # unique constraint covers — Postgres can use that constraint's own
    # index for lookups, so no separate index is needed.


def downgrade() -> None:
    op.drop_table("idempotency_keys")
