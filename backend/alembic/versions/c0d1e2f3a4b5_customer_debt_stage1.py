"""customer accounts and debt management, stage 1

Adds customers, payments, payment_allocations, opening_balances and the
append-only customer_ledger_entries; links sales to customers; adds credit
given / debt collected to daily_closings. Additive only: every existing sale
gains one backfilled payment + allocation, nothing else changes.

Revision ID: c0d1e2f3a4b5
Revises: f1a2b3c4d5e6
Create Date: 2026-11-26 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'c0d1e2f3a4b5'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None

TZ = "Africa/Dar_es_Salaam"


def _ts(name, **kw):
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_customer_number START 1 INCREMENT 1 NO CYCLE")
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_payment_number START 1 INCREMENT 1 NO CYCLE")

    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("customer_no", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False, unique=True),
        sa.Column("email", sa.String(150)),
        sa.Column("address", sa.String(255)),
        sa.Column("customer_type", sa.String(20), nullable=False, server_default="individual"),
        sa.Column("tin", sa.String(30)),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id")),
        _ts("created_at", nullable=False, server_default=sa.text("now()")),
        _ts("updated_at", nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "customer_type IN ('individual','business','institution','government')",
            name="chk_customers_type",
        ),
        sa.CheckConstraint("status IN ('active','inactive')", name="chk_customers_status"),
        sa.CheckConstraint("credit_limit >= 0", name="chk_customers_credit_limit"),
        sa.CheckConstraint("credit_days BETWEEN 0 AND 365", name="chk_customers_credit_days"),
    )

    op.create_table(
        "opening_balances",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("branch_id", sa.UUID(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("entered_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_by", sa.UUID(), sa.ForeignKey("users.id")),
        _ts("decided_at"),
        sa.Column("decision_note", sa.Text()),
        _ts("created_at", nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("amount > 0", name="chk_opening_balances_amount_pos"),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')", name="chk_opening_balances_status"
        ),
        sa.CheckConstraint(
            "decided_by IS NULL OR decided_by <> entered_by", name="chk_opening_balances_two_person"
        ),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("payment_no", sa.String(30), nullable=False, unique=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id")),
        sa.Column("branch_id", sa.UUID(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column(
            "method",
            postgresql.ENUM(name="payment_method_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("reference", sa.String(100)),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("received_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("reversed_by", sa.UUID(), sa.ForeignKey("users.id")),
        _ts("reversed_at"),
        sa.Column("reversal_reason", sa.Text()),
        sa.Column("balance_before", sa.Numeric(14, 2)),
        sa.Column("balance_after", sa.Numeric(14, 2)),
        _ts("created_at", nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("kind IN ('sale','debt')", name="chk_payments_kind"),
        sa.CheckConstraint("status IN ('active','reversed')", name="chk_payments_status"),
        sa.CheckConstraint("amount > 0", name="chk_payments_amount_pos"),
        sa.CheckConstraint(
            "kind <> 'debt' OR customer_id IS NOT NULL", name="chk_payments_debt_customer"
        ),
    )
    op.create_index("ix_payments_branch_created", "payments", ["branch_id", "created_at"])
    op.create_index("ix_payments_customer", "payments", ["customer_id"])

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("payment_id", sa.UUID(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("sale_id", sa.UUID(), sa.ForeignKey("sales.id")),
        sa.Column("opening_balance_id", sa.UUID(), sa.ForeignKey("opening_balances.id")),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("amount > 0", name="chk_allocations_amount_pos"),
        sa.CheckConstraint(
            "(sale_id IS NULL) <> (opening_balance_id IS NULL)", name="chk_allocations_one_target"
        ),
        sa.UniqueConstraint("payment_id", "sale_id", name="uq_allocations_payment_sale"),
        sa.UniqueConstraint("payment_id", "opening_balance_id", name="uq_allocations_payment_ob"),
    )
    op.create_index("ix_allocations_sale", "payment_allocations", ["sale_id"])
    op.create_index("ix_allocations_opening_balance", "payment_allocations", ["opening_balance_id"])

    op.create_table(
        "customer_ledger_entries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("branch_id", sa.UUID(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reverses_entry_id", sa.UUID(), sa.ForeignKey("customer_ledger_entries.id")),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "entry_type IN ('sale','payment','payment_reversal','sale_void','opening_balance')",
            name="chk_ledger_entry_type",
        ),
        sa.CheckConstraint(
            "debit >= 0 AND credit >= 0 AND (debit > 0) <> (credit > 0)",
            name="chk_ledger_one_side",
        ),
        sa.UniqueConstraint(
            "source_type", "source_id", "entry_type", name="uq_ledger_source_entry"
        ),
    )
    op.create_index(
        "ix_ledger_customer_branch", "customer_ledger_entries", ["customer_id", "branch_id"]
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION customer_ledger_append_only() RETURNS trigger AS $$
        BEGIN
            IF coalesce(current_setting('dukani.ledger_maintenance', true), '') = 'on' THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'customer_ledger_entries is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_ledger_append_only
        BEFORE UPDATE OR DELETE ON customer_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION customer_ledger_append_only()
        """
    )

    op.add_column("sales", sa.Column("customer_id", sa.UUID(), sa.ForeignKey("customers.id")))
    op.add_column("sales", sa.Column("due_date", sa.Date()))
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])
    op.alter_column("sales", "payment_method", nullable=True)

    op.add_column(
        "daily_closings",
        sa.Column("total_credit_given", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "daily_closings",
        sa.Column("total_debt_collected", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )

    # Backfill: every existing sale was paid in full by its single legacy
    # payment method — one payment + one allocation each. A voided sale's
    # payment is recorded as reversed with the void's who/when/why. The CTE
    # is materialized (volatile gen_random_uuid, referenced twice), so the
    # payment id is the same in both inserts.
    op.execute(
        f"""
        WITH src AS MATERIALIZED (
            SELECT s.id AS sale_id, gen_random_uuid() AS pid, s.*
            FROM sales s
            ORDER BY s.created_at, s.transaction_no
        ), ins AS (
            INSERT INTO payments (
                id, payment_no, kind, customer_id, branch_id, method, reference, amount,
                business_date, received_by, status, reversed_by, reversed_at,
                reversal_reason, created_at
            )
            SELECT
                pid,
                'PAY-' || to_char(created_at AT TIME ZONE '{TZ}', 'YYYYMMDD') || '-'
                    || lpad(nextval('seq_payment_number')::text, 4, '0'),
                'sale', NULL, branch_id, payment_method, payment_reference, total_amount,
                (created_at AT TIME ZONE '{TZ}')::date, cashier_id,
                CASE WHEN status = 'voided' THEN 'reversed' ELSE 'active' END,
                CASE WHEN status = 'voided' THEN voided_by END,
                CASE WHEN status = 'voided' THEN voided_at END,
                CASE WHEN status = 'voided' THEN void_reason END,
                created_at
            FROM src
            RETURNING id
        )
        INSERT INTO payment_allocations (id, payment_id, sale_id, opening_balance_id, amount)
        SELECT gen_random_uuid(), src.pid, src.sale_id, NULL, src.total_amount
        FROM src JOIN ins ON ins.id = src.pid
        """
    )


def downgrade() -> None:
    # Give every sale back a legacy payment method: its first payment's, or
    # 'cash' for a sale that had none (a full-credit sale has no payment).
    op.execute(
        """
        UPDATE sales s SET
            payment_method = coalesce(fp.method, 'cash'),
            payment_reference = fp.reference
        FROM sales s2
        LEFT JOIN LATERAL (
            SELECT p.method, p.reference
            FROM payment_allocations a JOIN payments p ON p.id = a.payment_id
            WHERE a.sale_id = s2.id AND p.kind = 'sale'
            ORDER BY p.created_at, p.payment_no
            LIMIT 1
        ) fp ON true
        WHERE s.id = s2.id AND s.payment_method IS NULL
        """
    )
    op.alter_column("sales", "payment_method", nullable=False)
    op.drop_column("daily_closings", "total_debt_collected")
    op.drop_column("daily_closings", "total_credit_given")
    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_column("sales", "due_date")
    op.drop_column("sales", "customer_id")
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_append_only ON customer_ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS customer_ledger_append_only()")
    op.drop_table("customer_ledger_entries")
    op.drop_table("payment_allocations")
    op.drop_table("payments")
    op.drop_table("opening_balances")
    op.drop_table("customers")
    op.execute("DROP SEQUENCE IF EXISTS seq_payment_number")
    op.execute("DROP SEQUENCE IF EXISTS seq_customer_number")
