"""Customer account statement (brief §13), read straight from the
append-only ledger: opening balance before the range, each entry in the
range with a running balance, and the closing balance — which is, by
construction, the ledger balance at the end of the range."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, debt_error
from app.models.branch import Branch
from app.models.customer import Customer
from app.models.customer_ledger import CustomerLedgerEntry as L
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment
from app.models.sale import Sale
from app.schemas.customer import CustomerRef
from app.schemas.debt import StatementLine, StatementOut
from app.services.ledger_service import CENT, OPENING_BALANCE_PREFIX

ZERO = Decimal("0.00")


async def statement(
    db: AsyncSession, customer_id: UUID, branch_id: UUID | None, date_from: date, date_to: date
) -> StatementOut:
    if date_from > date_to:
        raise debt_error("DATE_RANGE_INVALID")
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise NotFoundException("Mteja", "customer")

    scope = [L.customer_id == customer_id]
    if branch_id is not None:
        scope.append(L.branch_id == branch_id)

    opening = (await db.execute(
        select(func.coalesce(func.sum(L.debit - L.credit), 0)).where(*scope, L.business_date < date_from)
    )).scalar()
    opening = Decimal(opening).quantize(CENT)

    reference = case(
        (L.source_type == "sale", Sale.transaction_no),
        (L.source_type == "payment", Payment.payment_no),
        (L.source_type == "opening_balance", func.concat(OPENING_BALANCE_PREFIX, OpeningBalance.reference)),
        else_="",
    )
    rows = (await db.execute(
        select(L, Branch.name, reference)
        .join(Branch, Branch.id == L.branch_id)
        .outerjoin(Sale, and_(L.source_type == "sale", Sale.id == L.source_id))
        .outerjoin(Payment, and_(L.source_type == "payment", Payment.id == L.source_id))
        .outerjoin(OpeningBalance, and_(L.source_type == "opening_balance", OpeningBalance.id == L.source_id))
        .where(*scope, L.business_date >= date_from, L.business_date <= date_to)
        # Ties (rows written with one timestamp, e.g. demo data): charges first.
        .order_by(L.business_date, L.created_at, L.debit.desc(), L.id)
    )).all()

    balance = opening
    lines: list[StatementLine] = []
    for entry, branch_name, ref in rows:
        balance += entry.debit - entry.credit
        lines.append(StatementLine(
            date=entry.business_date, reference=ref or "", description=entry.description,
            entry_type=entry.entry_type, branch_name=branch_name,
            debit=entry.debit, credit=entry.credit, balance=balance,
        ))
    return StatementOut(
        customer=CustomerRef.model_validate(customer), branch_id=branch_id,
        date_from=date_from, date_to=date_to, opening_balance=opening, lines=lines,
        total_debit=sum((x.debit for x in lines), ZERO),
        total_credit=sum((x.credit for x in lines), ZERO),
        closing_balance=balance,
    )
