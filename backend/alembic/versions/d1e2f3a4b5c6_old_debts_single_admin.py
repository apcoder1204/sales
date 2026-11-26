"""old debts with a single admin: self-approval and cancellation

Each business has exactly one admin, so the two-person rule on old debts is
dropped (the admin checks and approves as a separate step). An approved old
debt with nothing paid on it can now be cancelled: status 'cancelled', who and
why, and an 'opening_void' ledger credit. Schema only; no rows are changed.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-11-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'd1e2f3a4b5c6'
down_revision = 'c0d1e2f3a4b5'
branch_labels = None
depends_on = None

LEDGER_TYPES = "'sale','payment','payment_reversal','sale_void','opening_balance'"


def upgrade() -> None:
    op.execute("ALTER TABLE opening_balances DROP CONSTRAINT chk_opening_balances_two_person")
    op.execute("ALTER TABLE opening_balances DROP CONSTRAINT chk_opening_balances_status")
    op.execute(
        "ALTER TABLE opening_balances ADD CONSTRAINT chk_opening_balances_status "
        "CHECK (status IN ('pending','approved','rejected','cancelled'))"
    )
    op.add_column("opening_balances", sa.Column(
        "cancelled_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("opening_balances", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("opening_balances", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.execute("ALTER TABLE customer_ledger_entries DROP CONSTRAINT chk_ledger_entry_type")
    op.execute(
        "ALTER TABLE customer_ledger_entries ADD CONSTRAINT chk_ledger_entry_type "
        f"CHECK (entry_type IN ({LEDGER_TYPES},'opening_void'))"
    )


def downgrade() -> None:
    # NOT VALID: rows written under the new rules (self-approved, cancelled,
    # opening_void) stay readable; only new writes are checked again.
    op.execute("ALTER TABLE customer_ledger_entries DROP CONSTRAINT chk_ledger_entry_type")
    op.execute(
        "ALTER TABLE customer_ledger_entries ADD CONSTRAINT chk_ledger_entry_type "
        f"CHECK (entry_type IN ({LEDGER_TYPES})) NOT VALID"
    )
    op.drop_column("opening_balances", "cancel_reason")
    op.drop_column("opening_balances", "cancelled_at")
    op.drop_column("opening_balances", "cancelled_by")
    op.execute("ALTER TABLE opening_balances DROP CONSTRAINT chk_opening_balances_status")
    op.execute(
        "ALTER TABLE opening_balances ADD CONSTRAINT chk_opening_balances_status "
        "CHECK (status IN ('pending','approved','rejected')) NOT VALID"
    )
    op.execute(
        "ALTER TABLE opening_balances ADD CONSTRAINT chk_opening_balances_two_person "
        "CHECK (decided_by IS NULL OR decided_by <> entered_by) NOT VALID"
    )
