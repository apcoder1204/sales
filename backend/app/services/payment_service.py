"""Payments: numbering, debt payments, reversals and receipts (spec §6.3)."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.business_time import business_date_today


async def next_payment_no(db: AsyncSession) -> str:
    seq = (await db.execute(text("SELECT nextval('seq_payment_number')"))).scalar()
    return f"PAY-{business_date_today().strftime('%Y%m%d')}-{seq:04d}"
