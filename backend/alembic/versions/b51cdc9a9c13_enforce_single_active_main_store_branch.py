"""enforce single active main store branch

Revision ID: b51cdc9a9c13
Revises: 44ed22b3b5a6
Create Date: 2026-09-21 11:21:15.234115

"""
from alembic import op
import sqlalchemy as sa


revision = 'b51cdc9a9c13'
down_revision = '44ed22b3b5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # get_main_store_id() does scalar_one_or_none() over
    # branch_type='main_store' AND is_active — a second active main store
    # (e.g. from a future seed/import mistake) would make that raise
    # MultipleResultsFound and take down every store_keeper/main-store flow
    # app-wide with a raw 500, not a clean business error. This partial
    # unique index makes that state impossible to insert in the first place.
    op.create_index(
        "uq_branches_single_active_main_store",
        "branches",
        ["branch_type"],
        unique=True,
        postgresql_where=sa.text("branch_type = 'main_store' AND is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_branches_single_active_main_store", table_name="branches")
