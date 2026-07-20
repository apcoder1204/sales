"""session/token hardening: token_version, current_refresh_jti, last_login_ip

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_login_ip', sa.String(45), nullable=True))
    op.add_column('users', sa.Column('token_version', sa.Integer, nullable=False, server_default='0'))
    op.add_column('users', sa.Column('current_refresh_jti', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'current_refresh_jti')
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'last_login_ip')
