from uuid import UUID
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class ReportFilter(BaseModel):
    period: Literal["today", "week", "month", "custom"] = "today"
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
