"""reconciliation runs and exceptions (customer debt, stage 3)

New tables and a sequence only; no existing rows change.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'f3a4b5c6d7e8'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def _uuid(name, fk=None, nullable=True):
    args = [sa.ForeignKey(fk)] if fk else []
    return sa.Column(name, postgresql.UUID(as_uuid=True), *args, nullable=nullable)


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_reconciliation_number START 1 INCREMENT 1 NO CYCLE")
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_no", sa.String(30), nullable=False, unique=True),
        sa.Column("scope", sa.String(10), nullable=False),
        _uuid("branch_id", "branches.id"),
        _uuid("customer_id", "customers.id"),
        _uuid("sale_id", "sales.id"),
        _uuid("payment_id", "payments.id"),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        _uuid("run_by", "users.id", nullable=False),
        sa.Column("records_examined", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discrepancy_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("scope IN ('all','branch','customer','sale','payment')", name="chk_recon_runs_scope"),
        sa.CheckConstraint("status IN ('PASSED','WARNING','FAILED')", name="chk_recon_runs_status"),
    )
    op.create_index("ix_recon_runs_created", "reconciliation_runs", ["created_at"])
    op.create_table(
        "reconciliation_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("check_group", sa.String(1), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("fingerprint", sa.String(200), nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="OPEN"),
        _uuid("first_run_id", "reconciliation_runs.id", nullable=False),
        _uuid("last_run_id", "reconciliation_runs.id", nullable=False),
        _uuid("customer_id", "customers.id"),
        _uuid("sale_id", "sales.id"),
        _uuid("payment_id", "payments.id"),
        _uuid("opening_balance_id", "opening_balances.id"),
        _uuid("closing_id", "daily_closings.id"),
        _uuid("branch_id", "branches.id"),
        sa.Column("expected", sa.Numeric(14, 2)),
        sa.Column("actual", sa.Numeric(14, 2)),
        sa.Column("difference", sa.Numeric(14, 2)),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_reason", sa.Text()),
        sa.Column("status_reference", sa.String(100)),
        _uuid("status_by", "users.id"),
        sa.Column("status_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("check_group IN ('A','B','C','D','E','F','G')", name="chk_recon_exc_group"),
        sa.CheckConstraint("severity IN ('money','warning')", name="chk_recon_exc_severity"),
        sa.CheckConstraint("status IN ('OPEN','UNDER_REVIEW','RESOLVED','DISMISSED')", name="chk_recon_exc_status"),
    )
    op.create_index("uq_recon_exception_live", "reconciliation_exceptions", ["fingerprint"], unique=True,
                    postgresql_where=sa.text("status IN ('OPEN','UNDER_REVIEW')"))
    op.create_index("ix_recon_exceptions_status", "reconciliation_exceptions", ["status", "detected_at"])


def downgrade() -> None:
    op.drop_index("ix_recon_exceptions_status", table_name="reconciliation_exceptions")
    op.drop_index("uq_recon_exception_live", table_name="reconciliation_exceptions")
    op.drop_table("reconciliation_exceptions")
    op.drop_index("ix_recon_runs_created", table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")
    op.execute("DROP SEQUENCE IF EXISTS seq_reconciliation_number")
