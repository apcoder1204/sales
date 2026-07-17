"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ENUMS
    op.execute("CREATE TYPE branch_type_enum AS ENUM ('main_store', 'pos_point')")
    op.execute("CREATE TYPE product_status_enum AS ENUM ('active', 'inactive', 'discontinued')")
    op.execute("""
        CREATE TYPE inv_transaction_type_enum AS ENUM (
            'stock_in','stock_out','sale','transfer_out','transfer_in','adjustment','damaged'
        )
    """)
    op.execute("CREATE TYPE payment_method_enum AS ENUM ('cash', 'mobile_money', 'bank_transfer')")
    op.execute("CREATE TYPE sale_status_enum AS ENUM ('completed', 'voided')")
    op.execute("CREATE TYPE request_status_enum AS ENUM ('pending', 'approved', 'rejected', 'fulfilled')")
    op.execute("CREATE TYPE transfer_status_enum AS ENUM ('completed', 'cancelled')")
    op.execute("""
        CREATE TYPE audit_category_enum AS ENUM (
            'authentication','products','inventory','sales','transfers','users','system'
        )
    """)

    # SEQUENCES
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_sale_number START 1 INCREMENT 1 NO CYCLE")
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_request_number START 1 INCREMENT 1 NO CYCLE")
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_transfer_number START 1 INCREMENT 1 NO CYCLE")

    # TABLES
    op.create_table("branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("branch_type", postgresql.ENUM("main_store", "pos_point", name="branch_type_enum", create_type=False), nullable=False, server_default="pos_point"),
        sa.Column("address", sa.Text),
        sa.Column("phone", sa.String(30)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table("roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text),
    )

    op.create_table("categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("name_sw", sa.String(100)),
        sa.Column("description", sa.Text),
    )

    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login", sa.TIMESTAMP(timezone=True)),
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("failed_login_attempts >= 0", name="chk_users_failed_login_min"),
    )
    op.create_index("idx_users_role_id", "users", ["role_id"])
    op.create_index("idx_users_branch_id", "users", ["branch_id"])

    op.create_table("products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("product_code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("brand", sa.String(100)),
        sa.Column("family_name", sa.String(100)),
        sa.Column("family_id", sa.String(50)),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("selling_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("minimum_stock", sa.Integer, nullable=False, server_default="5"),
        sa.Column("status", postgresql.ENUM("active", "inactive", "discontinued", name="product_status_enum", create_type=False), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("cost_price >= 0", name="chk_products_cost_positive"),
        sa.CheckConstraint("selling_price >= 0", name="chk_products_price_positive"),
        sa.CheckConstraint("minimum_stock >= 0", name="chk_products_min_stock"),
    )
    op.create_index("idx_products_category_id", "products", ["category_id"])
    op.create_index("idx_products_status", "products", ["status"])
    op.execute("CREATE INDEX idx_products_name_trgm ON products USING GIN (name gin_trgm_ops)")

    op.create_table("inventory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reserved_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("product_id", "branch_id", name="uq_inventory_product_branch"),
        sa.CheckConstraint("quantity >= 0", name="chk_inventory_qty_non_negative"),
        sa.CheckConstraint("reserved_qty >= 0", name="chk_inventory_reserved_pos"),
        sa.CheckConstraint("reserved_qty <= quantity", name="chk_inventory_reserved_lte_qty"),
    )
    op.create_index("idx_inventory_product_id", "inventory", ["product_id"])
    op.create_index("idx_inventory_branch_id", "inventory", ["branch_id"])

    op.create_table("inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("transaction_type", postgresql.ENUM("stock_in","stock_out","sale","transfer_out","transfer_in","adjustment","damaged", name="inv_transaction_type_enum", create_type=False), nullable=False),
        sa.Column("quantity_before", sa.Integer, nullable=False),
        sa.Column("quantity_change", sa.Integer, nullable=False),
        sa.Column("quantity_after", sa.Integer, nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reference_type", sa.String(20)),
        sa.Column("notes", sa.Text),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("quantity_after >= 0", name="chk_inv_tx_qty_after_non_neg"),
        sa.CheckConstraint("quantity_after = quantity_before + quantity_change", name="chk_inv_tx_math"),
    )
    op.create_index("idx_inv_tx_product_branch_date", "inventory_transactions", ["product_id", "branch_id", "created_at"])
    op.create_index("idx_inv_tx_performed_by", "inventory_transactions", ["performed_by"])

    op.create_table("sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("transaction_no", sa.String(30), nullable=False, unique=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("cashier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(6, 4), nullable=False, server_default="0.1800"),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", postgresql.ENUM("cash","mobile_money","bank_transfer", name="payment_method_enum", create_type=False), nullable=False),
        sa.Column("payment_reference", sa.String(100)),
        sa.Column("status", postgresql.ENUM("completed","voided", name="sale_status_enum", create_type=False), nullable=False, server_default="completed"),
        sa.Column("voided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("voided_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("void_reason", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("subtotal >= 0", name="chk_sales_subtotal_pos"),
        sa.CheckConstraint("total_amount > 0", name="chk_sales_total_pos"),
    )
    op.create_index("idx_sales_branch_date", "sales", ["branch_id", "created_at"])
    op.create_index("idx_sales_cashier_id", "sales", ["cashier_id"])
    op.create_index("idx_sales_created_at", "sales", ["created_at"])

    op.create_table("sale_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="chk_sale_items_qty_pos"),
    )
    op.create_index("idx_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("idx_sale_items_product_id", "sale_items", ["product_id"])

    op.create_table("stock_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("request_no", sa.String(30), nullable=False, unique=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("from_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("to_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("main_store_had_stock", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("status", postgresql.ENUM("pending","approved","rejected","fulfilled", name="request_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("review_notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("quantity > 0", name="chk_stock_req_qty_pos"),
        sa.CheckConstraint("from_branch_id != to_branch_id", name="chk_stock_req_diff_branches"),
    )
    op.create_index("idx_stock_req_status", "stock_requests", ["status"])
    op.create_index("idx_stock_req_created_at", "stock_requests", ["created_at"])

    op.create_table("stock_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("transfer_no", sa.String(30), nullable=False, unique=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_requests.id")),
        sa.Column("from_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("to_branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("transferred_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", postgresql.ENUM("completed","cancelled", name="transfer_status_enum", create_type=False), nullable=False, server_default="completed"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint("from_branch_id != to_branch_id", name="chk_stock_tf_diff_branches"),
    )

    op.create_table("stock_transfer_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.CheckConstraint("quantity > 0", name="chk_tf_items_qty_pos"),
    )

    op.create_table("audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("user_role", sa.String(50), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("category", postgresql.ENUM("authentication","products","inventory","sales","transfers","users","system", name="audit_category_enum", create_type=False), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("details", postgresql.JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_audit_category_date", "audit_logs", ["category", "created_at"])
    op.create_index("idx_audit_user_date", "audit_logs", ["user_id", "created_at"])
    op.create_index("idx_audit_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    for table in ["audit_logs","stock_transfer_items","stock_transfers","stock_requests",
                  "sale_items","sales","inventory_transactions","inventory",
                  "products","users","categories","roles","branches"]:
        op.drop_table(table)
    for enum in ["audit_category_enum","transfer_status_enum","request_status_enum",
                 "sale_status_enum","payment_method_enum","inv_transaction_type_enum",
                 "product_status_enum","branch_type_enum"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
    for seq in ["seq_sale_number","seq_request_number","seq_transfer_number"]:
        op.execute(f"DROP SEQUENCE IF EXISTS {seq}")
