"""Reconciliation checks over a period — E (sales), F (P&L), G (daily
closing and payment references) — and find_all's scope table. Stage 3
plan Task 3, brief §19 E–G."""
from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.core.business_time import _TZ, UTC, business_date_today, utc_range_for_business_date
from app.models.daily_closing import DailyClosing
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.services import reconciliation_checks as rc
from tests.conftest import auth_headers
from tests.test_recon_documents import ReconWorld

D = Decimal


@pytest.fixture
async def rw(db_session, client):
    return await ReconWorld(db_session, client).build()


async def close_day(rw, branch=None):
    r = await rw.client.post("/api/v1/closings/close", json={"branch_id": str((branch or rw.a).id)},
                             headers=auth_headers(rw.admin))
    assert r.status_code == 201, r.text
    return (await rw.db.execute(select(DailyClosing).where(DailyClosing.id == r.json()["id"])
                                .execution_options(populate_existing=True))).scalar_one()


def codes(findings):
    return sorted(f.code for f in findings)


@pytest.mark.asyncio
async def test_voided_sale_active_payment_is_orphan(rw):
    sale = await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    await rw.void(sale)
    assert (await rc.find_all(rw.db, rw.scope())).findings == []
    [p] = await rw.payments_of(sale)
    await rw.db.execute(update(Payment).where(Payment.id == p.id).values(status="active"))
    await rw.db.flush()
    assert "ORPHAN_ALLOCATION" in codes((await rc.find_all(rw.db, rw.scope())).findings)


@pytest.mark.asyncio
async def test_period_summary_figures(rw):
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    await rw.sale(4, payments=[{"method": "cash", "amount": "150000"}])
    await rw.debt_pay(50000)
    voided = await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    await rw.void(voided)
    res = await rc.check_sales_period(rw.db, rw.scope())
    s = res.summary["branches"][rw.a.id]
    assert {k: s[k] for k in ("sales_total", "till_collected", "credit_given", "debt_collected",
                              "voided_count", "voided_total")} == {
        "sales_total": D(500000), "till_collected": D(250000), "credit_given": D(250000),
        "debt_collected": D(50000), "voided_count": 1, "voided_total": D(100000),
    }
    assert res.findings == []


@pytest.mark.asyncio
async def test_pnl_consistency(rw):
    sale = await rw.sale(4, payments=[{"method": "cash", "amount": "150000"}])
    await rw.debt_pay(100000)
    res = await rc.check_pnl(rw.db, rw.scope())
    assert res.findings == []
    assert res.summary["branches"][rw.a.id]["pnl_revenue"] == D(400000)
    await rw.db.execute(update(SaleItem).where(SaleItem.sale_id == sale).values(line_total=D(390000)))
    await rw.db.flush()
    [f] = (await rc.check_pnl(rw.db, rw.scope())).findings
    assert (f.code, f.expected, f.actual, f.branch_id) == ("PNL_REVENUE_MISMATCH", D(400000), D(390000), rw.a.id)
    assert "SALE_ITEMS_MISMATCH" in codes((await rc.find_all(rw.db, rw.scope())).findings)


@pytest.mark.asyncio
async def test_closing_consistency(rw):
    await rw.sale(4, payments=[{"method": "cash", "amount": "150000"}])
    await rw.debt_pay(50000, method="mobile_money", reference="MPC1")
    await rw.sale(1, customer=False, payments=[{"method": "bank_transfer", "amount": "100000", "reference": "BK1"}])
    c = await close_day(rw)
    assert (await rc.check_closings(rw.db, rw.scope())).findings == []
    await rw.db.execute(update(DailyClosing).where(DailyClosing.id == c.id)
                        .values(total_cash=c.total_cash + D(1000)))
    await rw.db.flush()
    [f] = (await rc.check_closings(rw.db, rw.scope())).findings
    assert (f.code, f.detail, f.difference, f.closing_id) == ("CLOSING_TOTAL_MISMATCH", "total_cash", D(1000), c.id)


@pytest.mark.asyncio
async def test_closing_reopened_and_reclosed_is_clean(rw):
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    c = await close_day(rw)
    r = await rw.client.put(f"/api/v1/closings/{c.id}/reopen", json={"reason": "Mauzo yaliyosahaulika"},
                            headers=auth_headers(rw.admin))
    assert r.status_code == 200, r.text
    await rw.sale(2, payments=[{"method": "cash", "amount": "50000"}])
    await rw.debt_pay(30000)
    await close_day(rw)
    assert (await rc.find_all(rw.db, rw.scope())).findings == []


@pytest.mark.asyncio
async def test_closing_without_opened_at_uses_business_day(rw):
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    c = await close_day(rw)
    assert c.opened_at is None
    day_start, day_end = utc_range_for_business_date(c.business_date)
    assert rc.closing_window(c) == (day_start, min(day_end, c.closed_at.replace(tzinfo=None)))
    assert (await rc.check_closings(rw.db, rw.scope())).findings == []


@pytest.mark.asyncio
async def test_period_uses_tanzania_dates(rw):
    today = business_date_today()
    sale = await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    # 00:30 local today = 21:30 UTC on the previous calendar day.
    local = datetime.combine(today, time(0, 30), tzinfo=_TZ)
    utc_naive = local.astimezone(UTC).replace(tzinfo=None)
    assert utc_naive.date() == today - timedelta(days=1)
    await rw.db.execute(update(Sale).where(Sale.id == sale).values(created_at=utc_naive))
    [p] = await rw.payments_of(sale)
    await rw.db.execute(update(Payment).where(Payment.id == p.id).values(created_at=local))
    await rw.db.flush()

    def period(day):
        return rc.Scope(kind="branch", branch_id=rw.a.id, date_from=day, date_to=day)

    on_day = (await rc.check_sales_period(rw.db, period(today))).summary["branches"][rw.a.id]
    assert (on_day["sales_total"], on_day["till_collected"]) == (D(100000), D(100000))
    before = (await rc.check_sales_period(rw.db, period(today - timedelta(days=1)))).summary["branches"]
    assert rw.a.id not in before or before[rw.a.id]["sales_total"] == 0


@pytest.mark.asyncio
async def test_duplicate_payment_reference_is_warning(rw):
    await rw.sale(3)
    await rw.debt_pay(50000, method="mobile_money", reference=" mp123 ")
    await rw.debt_pay(50000, method="mobile_money", reference="MP123")
    [f] = (await rc.check_closings(rw.db, rw.scope())).findings
    assert (f.code, f.severity) == ("DUPLICATE_PAYMENT_REFERENCE", "warning")
    assert f.detail.count("PAY-") == 2


@pytest.mark.asyncio
async def test_scope_table(rw):
    await rw.sale(3)
    p1 = await rw.debt_pay(50000, method="mobile_money", reference="DUP9")
    await rw.debt_pay(50000, method="mobile_money", reference="DUP9")
    c = await close_day(rw)
    await rw.db.execute(update(DailyClosing).where(DailyClosing.id == c.id).values(total_revenue=D(1)))
    await rw.db.flush()
    branch = codes((await rc.find_all(rw.db, rw.scope())).findings)
    assert branch == ["CLOSING_TOTAL_MISMATCH", "DUPLICATE_PAYMENT_REFERENCE"]
    assert codes((await rc.find_all(rw.db, rw.scope("customer"))).findings) == []
    assert codes((await rc.find_all(rw.db, rw.scope("payment", payment_id=p1))).findings) == [
        "DUPLICATE_PAYMENT_REFERENCE"]


@pytest.mark.asyncio
async def test_second_register_same_day_is_clean(rw):
    """Review finding 1: a register closed without an explicit opening, then
    a second register the same day. The first register's figures are what
    existed when it closed; the second register's sales are not its own."""
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    c1 = await close_day(rw)
    assert c1.opened_at is None
    r = await rw.client.post("/api/v1/closings/open", json={"branch_id": str(rw.a.id), "opening_cash": "0"},
                             headers=auth_headers(rw.admin))
    assert r.status_code == 201, r.text
    # Register 2's sale happens after register 1 closed (the test transaction's
    # now() is frozen, so place it explicitly).
    sale = await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    later = c1.closed_at.replace(tzinfo=None) + timedelta(minutes=5)
    await rw.db.execute(update(Sale).where(Sale.id == sale).values(created_at=later))
    [p] = await rw.payments_of(sale)
    await rw.db.execute(update(Payment).where(Payment.id == p.id).values(created_at=later.replace(tzinfo=UTC)))
    await rw.db.flush()
    assert (await rc.check_closings(rw.db, rw.scope())).findings == []
