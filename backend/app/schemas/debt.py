"""Stage 2 read models: statements, ageing, dashboard, risk, follow-ups and
debt reports. All amounts are Decimal; nothing here writes money."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.customer import CustomerRef


class StatementLine(BaseModel):
    date: date
    reference: str
    description: str
    entry_type: str
    branch_name: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class StatementOut(BaseModel):
    customer: CustomerRef
    branch_id: UUID | None
    date_from: date
    date_to: date
    opening_balance: Decimal
    lines: list[StatementLine]
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
