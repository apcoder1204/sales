from app.db.base_class import Base  # noqa — re-export for Alembic env.py

# Import all models here so Alembic can detect them
from app.models.branch import Branch  # noqa
from app.models.role import Role  # noqa
from app.models.user import User  # noqa
from app.models.category import Category  # noqa
from app.models.product import Product  # noqa
from app.models.inventory import Inventory  # noqa
from app.models.inventory_transaction import InventoryTransaction  # noqa
from app.models.sale import Sale  # noqa
from app.models.sale_item import SaleItem  # noqa
from app.models.stock_request import StockRequest  # noqa
from app.models.stock_request_item import StockRequestItem  # noqa
from app.models.stock_transfer import StockTransfer  # noqa
from app.models.stock_transfer_item import StockTransferItem  # noqa
from app.models.audit_log import AuditLog  # noqa
from app.models.daily_closing import DailyClosing  # noqa
from app.models.daily_closing_expense import DailyClosingExpense  # noqa
