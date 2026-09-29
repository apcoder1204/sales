from uuid import UUID
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class ReportFilter(BaseModel):
    period: Literal["today", "yesterday", "week", "month", "last_month", "custom"] = "today"
    from_date: date | None = None
    to_date: date | None = None
    branch_id: UUID | None = None


class ChartPoint(BaseModel):
    label: str
    value: float


class SalesSummary(BaseModel):
    total_revenue: float
    total_transactions: int
    avg_transaction: float
    total_items_sold: int


class TopProduct(BaseModel):
    product: str
    qty_sold: int
    revenue: float


class PaymentBreakdown(BaseModel):
    method: str
    count: int
    total: float


class SalesReportResponse(BaseModel):
    summary: SalesSummary
    chart_data: list[ChartPoint]
    top_products: list[TopProduct]
    payment_breakdown: list[PaymentBreakdown]
    generated_at: datetime


class InventorySummary(BaseModel):
    total_products: int
    total_quantity: int
    total_value: float
    low_stock_count: int


class BranchInventory(BaseModel):
    branch: str
    total_quantity: int
    total_value: float
    low_stock_count: int


class LowStockItem(BaseModel):
    product: str
    product_code: str
    branch: str
    current_stock: int
    minimum_stock: int
    deficit: int


class InventoryReportResponse(BaseModel):
    summary: InventorySummary
    by_branch: list[BranchInventory]
    low_stock_items: list[LowStockItem]
    generated_at: datetime


class BranchPerformance(BaseModel):
    branch: str
    total_revenue: float
    transaction_count: int
    avg_transaction: float
    items_sold: int


class BranchPerformanceResponse(BaseModel):
    branches: list[BranchPerformance]
    chart_data: list[ChartPoint]
    generated_at: datetime


class CashierPerformance(BaseModel):
    cashier: str
    branch: str
    total_revenue: float
    transaction_count: int
    avg_transaction: float
    items_sold: int


class CashierPerformanceResponse(BaseModel):
    cashiers: list[CashierPerformance]
    generated_at: datetime


class ClosingReportExpense(BaseModel):
    description: str
    amount: float


class ClosingReportRow(BaseModel):
    business_date: date
    branch: str
    status: str
    total_cash: float
    total_mobile_money: float
    total_bank_transfer: float
    total_revenue: float
    cash_variance: float | None
    total_expenses: float
    expenses: list[ClosingReportExpense]
    closed_by: str | None


class ClosingReportSummary(BaseModel):
    total_cash: float
    total_mobile_money: float
    total_bank_transfer: float
    total_revenue: float
    closings_count: int


class ClosingReportResponse(BaseModel):
    summary: ClosingReportSummary
    closings: list[ClosingReportRow]
    generated_at: datetime


# ── Profit & Loss ────────────────────────────────────────────────────────────

class ProfitLossPeriod(BaseModel):
    start: date
    end: date


class ProfitLossBranchInfo(BaseModel):
    id: UUID
    name: str


class ProfitLossSummary(BaseModel):
    revenue: float
    cost_of_goods_sold: float
    gross_profit: float
    gross_margin: float | None
    operating_expenses: float
    net_profit: float
    net_margin: float | None
    status: Literal["profit", "loss", "break_even"]


class BranchProfitLoss(BaseModel):
    branch_id: UUID
    branch: str
    revenue: float
    cost_of_goods_sold: float
    gross_profit: float
    gross_margin: float | None
    operating_expenses: float
    net_profit: float
    net_margin: float | None
    status: Literal["profit", "loss", "break_even"]


class ProductProfitability(BaseModel):
    product_id: UUID
    product: str
    quantity_sold: int
    revenue: float
    cost_of_goods_sold: float
    gross_profit: float
    gross_margin: float | None


class CategoryProfitability(BaseModel):
    category_id: int
    category: str
    revenue: float
    cost_of_goods_sold: float
    gross_profit: float
    gross_margin: float | None


class ProfitLossResponse(BaseModel):
    period: ProfitLossPeriod
    # None means a consolidated "ALL branches" view (global roles only —
    # branch_context already enforces this server-side).
    branch: ProfitLossBranchInfo | None
    summary: ProfitLossSummary
    # Populated only for the consolidated ALL-branches view — a single
    # already-scoped branch's breakdown would just repeat `summary`.
    branches: list[BranchProfitLoss]
    products: list[ProductProfitability]
    categories: list[CategoryProfitability]
    generated_at: datetime
