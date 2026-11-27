"""Reconciliation checks A (sales and receivables), B (payment allocation)
and C (customer ledger) — stage 3 plan Task 2, brief §19 A–C and the
reconciliation tests of §31. Corrupt data is written straight through the
session (ledger rows under the maintenance flag), never through the API,
because the API refuses to create it."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text, update

from app.core.business_time import business_date_today
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.opening_balance import OpeningBalance
from app.models.payment import Payment, PaymentAllocation
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.services import reconciliation_checks as rc
from tests.conftest import auth_headers, make_customer
from tests.test_debt_payments import World

D = Decimal


class ReconWorld(World):
    """World plus the documents and corruptions the reconciliation tests need."""

    async def sale(self, qty, payments=(), customer=True, branch=None, cashier=None):
        branch, cashier = branch or self.a, cashier or self.cashier_a
        body = {"branch_id": str(branch.id), "payments": list(payments),
                "items": [{"product_id": str(self.product.id), "quantity": qty}]}
        if customer:
            body["customer_id"] = str(self.customer.id)
        r = await self.client.post("/api/v1/sales", json=body, headers=auth_headers(cashier))
        assert r.status_code == 201, r.text
        return uuid.UUID(r.json()["sale"]["id"])

    async def debt_pay(self, amount, method="cash", user=None, reference=None):
        body = {"method": method, "amount": str(amount)}
        if reference is not None:
            body["reference"] = reference
        r = await self.pay(user or self.cashier_a, body)
        assert r.status_code == 201, r.text
        return uuid.UUID(r.json()["id"])

    async def reverse(self, payment_id):
        r = await self.client.post(f"/api/v1/payments/{payment_id}/reverse", json={"reason": "Kimakosa kabisa"},
                                   headers=auth_headers(self.admin))
        assert r.status_code == 200, r.text

    async def void(self, sale_id):
        r = await self.client.post(f"/api/v1/sales/{sale_id}/void", json={"reason": "Kosa la mfumo"},
                                   headers=auth_headers(self.admin))
        assert r.status_code == 200, r.text

    async def old_debt(self, amount, approve=True, branch=None):
        r = await self.client.post(f"/api/v1/customers/{self.customer.id}/opening-balances", json={
            "branch_id": str((branch or self.a).id), "amount": str(amount),
            "reference": f"DAFTARI-{uuid.uuid4().hex[:6]}", "effective_date": business_date_today().isoformat(),
        }, headers=auth_headers(self.admin))
        assert r.status_code == 201, r.text
        ob_id = uuid.UUID(r.json()["id"])
        if approve:
            r = await self.client.post(f"/api/v1/opening-balances/{ob_id}/approve", json={},
                                       headers=auth_headers(self.admin))
            assert r.status_code == 200, r.text
        return ob_id

    async def maintenance(self):
        await self.db.execute(text("SET LOCAL dukani.ledger_maintenance = 'on'"))

    async def payments_of(self, sale_id):
        return (await self.db.execute(
            select(Payment).join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
            .where(PaymentAllocation.sale_id == sale_id)
        )).scalars().all()

    def scope(self, kind="branch", **ids):
        if kind == "branch" and not ids:
            ids = {"branch_id": self.a.id}
        if kind == "customer" and not ids:
            ids = {"customer_id": self.customer.id}
        today = business_date_today()
        return rc.Scope(kind=kind, date_from=today, date_to=today, **ids)


@pytest.fixture
async def rw(db_session, client):
    return await ReconWorld(db_session, client).build()


def codes(result):
    return sorted((f.code, f.expected, f.actual) for f in result.findings)


async def abc(rw, scope=None):
    scope = scope or rw.scope()
    out = []
    for fn in (rc.check_receivables, rc.check_allocations, rc.check_ledger):
        out += (await fn(rw.db, scope)).findings
    return out


@pytest.mark.asyncio
async def test_correct_sale_payment_receivable_is_clean(rw):
    await rw.sale(4, payments=[{"method": "cash", "amount": "150000"}])
    await rw.debt_pay(100000)
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    assert await abc(rw) == []
    assert await abc(rw, rw.scope("customer")) == []


@pytest.mark.asyncio
async def test_receivable_overpaid(rw):
    """The "duplicate allocation" of brief §31: one debt settled twice."""
    sale = await rw.sale(4, payments=[{"method": "cash", "amount": "150000"}])
    await rw.debt_pay(250000)  # settles the sale in full
    await rw.sale(1)
    p2 = await rw.debt_pay(50000)  # allocated to the second sale...
    await rw.db.execute(update(PaymentAllocation).where(PaymentAllocation.payment_id == p2)
                        .values(sale_id=sale))  # ...moved onto the settled one
    await rw.db.flush()
    assert codes(await rc.check_receivables(rw.db, rw.scope())) == [("RECEIVABLE_OVERPAID", D(400000), D(450000))]


@pytest.mark.asyncio
async def test_walkin_sale_unpaid(rw):
    sale = await rw.sale(2, customer=False, payments=[{"method": "cash", "amount": "200000"}])
    [p] = await rw.payments_of(sale)
    await rw.db.execute(update(PaymentAllocation).where(PaymentAllocation.payment_id == p.id)
                        .values(amount=D(150000)))
    await rw.db.flush()
    found = codes(await rc.check_receivables(rw.db, rw.scope()))
    assert found == [("WALKIN_SALE_UNPAID", D(200000), D(150000))]
    # ...and the till payment no longer allocates its full amount.
    assert ("ALLOCATION_TOTAL_MISMATCH", D(200000), D(150000)) in codes(await rc.check_allocations(rw.db, rw.scope()))


@pytest.mark.asyncio
async def test_sale_items_mismatch(rw):
    sale = await rw.sale(2, customer=False, payments=[{"method": "cash", "amount": "200000"}])
    await rw.db.execute(update(SaleItem).where(SaleItem.sale_id == sale).values(line_total=D(190000)))
    await rw.db.flush()
    assert codes(await rc.check_receivables(rw.db, rw.scope())) == [("SALE_ITEMS_MISMATCH", D(190000), D(200000))]


@pytest.mark.asyncio
async def test_legacy_sale_clean_and_mismatch_is_warning(rw):
    sale = await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    # A backfilled pre-debt sale: legacy column set, one matching till payment.
    await rw.db.execute(update(Sale).where(Sale.id == sale).values(payment_method="cash"))
    await rw.db.flush()
    assert (await rc.check_receivables(rw.db, rw.scope())).findings == []
    await rw.db.execute(update(Sale).where(Sale.id == sale).values(payment_method="mobile_money"))
    await rw.db.flush()
    [f] = (await rc.check_receivables(rw.db, rw.scope())).findings
    assert (f.code, f.severity, f.expected, f.actual) == ("LEGACY_PAYMENT_MISMATCH", "warning", D(100000), D(100000))


@pytest.mark.asyncio
async def test_missing_allocation(rw):
    await rw.sale(3)
    p = await rw.debt_pay(100000)
    await rw.db.execute(delete(PaymentAllocation).where(PaymentAllocation.payment_id == p))
    await rw.db.flush()
    assert codes(await rc.check_allocations(rw.db, rw.scope())) == [("ALLOCATION_TOTAL_MISMATCH", D(100000), D(0))]
    # The sale now looks unpaid while the ledger has the payment credit.
    assert codes(await rc.check_ledger(rw.db, rw.scope())) == [("LEDGER_BALANCE_MISMATCH", D(300000), D(200000))]


@pytest.mark.asyncio
async def test_allocation_branch_and_customer_mismatch(rw):
    sale_b = await rw.sale(1, branch=rw.b, cashier=rw.cashier_b)
    await rw.sale(1)
    p = await rw.debt_pay(100000)
    stranger = await make_customer(rw.db, credit_limit=D(1000000))
    await rw.db.execute(update(Sale).where(Sale.id == sale_b).values(customer_id=stranger.id))
    await rw.db.execute(update(PaymentAllocation).where(PaymentAllocation.payment_id == p).values(sale_id=sale_b))
    await rw.db.flush()
    found = sorted(f.code for f in (await rc.check_allocations(rw.db, rw.scope())).findings)
    assert found == ["ALLOCATION_BRANCH_MISMATCH", "ALLOCATION_CUSTOMER_MISMATCH"]


@pytest.mark.asyncio
async def test_orphaned_allocation(rw):
    ob = await rw.old_debt(80000)
    await rw.debt_pay(30000)
    await rw.db.execute(update(OpeningBalance).where(OpeningBalance.id == ob).values(status="rejected"))
    await rw.db.flush()
    found = codes(await rc.check_allocations(rw.db, rw.scope()))
    assert ("ORPHAN_ALLOCATION", D(0), D(30000)) in found
    # A voided sale that still carries an active payment is orphaned too.
    sale = await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    await rw.db.execute(update(Sale).where(Sale.id == sale).values(status="voided"))
    await rw.db.flush()
    found = codes(await rc.check_allocations(rw.db, rw.scope()))
    assert ("ORPHAN_ALLOCATION", D(0), D(100000)) in found


@pytest.mark.asyncio
async def test_reversed_payment_is_clean(rw):
    await rw.sale(3, payments=[{"method": "mobile_money", "amount": "50000", "reference": "MPX1"}])
    p = await rw.debt_pay(100000)
    await rw.reverse(p)
    ob = await rw.old_debt(40000)
    r = await rw.client.post(f"/api/v1/opening-balances/{ob}/cancel", json={"reason": "Imeingizwa mara mbili"},
                             headers=auth_headers(rw.admin))
    assert r.status_code == 200, r.text
    voided = await rw.sale(1, payments=[{"method": "cash", "amount": "20000"}])
    await rw.void(voided)
    assert await abc(rw) == []
    assert await abc(rw, rw.scope("customer")) == []


@pytest.mark.asyncio
async def test_missing_and_mismatched_ledger_entry(rw):
    sale = await rw.sale(2)
    p = await rw.debt_pay(50000)
    await rw.maintenance()
    await rw.db.execute(delete(CustomerLedgerEntry).where(
        CustomerLedgerEntry.source_id == sale, CustomerLedgerEntry.entry_type == "sale"))
    await rw.db.execute(update(CustomerLedgerEntry).where(
        CustomerLedgerEntry.source_id == p, CustomerLedgerEntry.entry_type == "payment").values(credit=D(40000)))
    await rw.db.flush()
    found = (await rc.check_ledger(rw.db, rw.scope())).findings
    by_code = {f.code: f for f in found}
    assert (by_code["MISSING_LEDGER_ENTRY"].expected, by_code["MISSING_LEDGER_ENTRY"].actual) == (D(200000), D(0))
    m = by_code["LEDGER_ENTRY_MISMATCH"]
    assert (m.detail, m.expected, m.actual, m.payment_id) == ("amount", D(50000), D(40000), p)
    assert "LEDGER_BALANCE_MISMATCH" in by_code


@pytest.mark.asyncio
async def test_orphan_ledger_entry(rw):
    sale = await rw.sale(1)
    await rw.db.execute(text(
        "INSERT INTO customer_ledger_entries (id, customer_id, branch_id, entry_type, source_type, source_id,"
        " debit, credit, business_date, description, created_by)"
        " VALUES (:id, :c, :b, 'sale_void', 'sale', :s, 0, 100000, :d, 'x', :u)"
    ), {"id": uuid.uuid4(), "c": rw.customer.id, "b": rw.a.id, "s": sale, "d": business_date_today(),
        "u": rw.admin.id})
    await rw.db.flush()
    found = codes(await rc.check_ledger(rw.db, rw.scope()))
    assert ("ORPHAN_LEDGER_ENTRY", D(0), D(100000)) in found


@pytest.mark.asyncio
async def test_cached_balance_mismatch(rw):
    await rw.sale(2)
    await rw.db.execute(text(
        "INSERT INTO customer_ledger_entries (id, customer_id, branch_id, entry_type, source_type, source_id,"
        " debit, credit, business_date, description, created_by)"
        " VALUES (:id, :c, :b, 'opening_balance', 'opening_balance', :s, 5000, 0, :d, 'x', :u)"
    ), {"id": uuid.uuid4(), "c": rw.customer.id, "b": rw.a.id, "s": uuid.uuid4(), "d": business_date_today(),
        "u": rw.admin.id})
    await rw.db.flush()
    [bal] = [f for f in (await rc.check_ledger(rw.db, rw.scope())).findings if f.code == "LEDGER_BALANCE_MISMATCH"]
    assert (bal.expected, bal.actual, bal.difference) == (D(200000), D(205000), D(5000))
    assert (bal.customer_id, bal.branch_id) == (rw.customer.id, rw.a.id)


@pytest.mark.asyncio
async def test_customer_scope_only_that_customer(rw):
    await rw.sale(1)
    other = await make_customer(rw.db, credit_limit=D(1000000))
    keep, rw.customer = rw.customer, other
    sale = await rw.sale(2)
    rw.customer = keep
    await rw.db.execute(update(SaleItem).where(SaleItem.sale_id == sale).values(line_total=D(1)))
    await rw.db.flush()
    assert await abc(rw, rw.scope("customer")) == []
    assert [f.code for f in await abc(rw, rw.scope("customer", customer_id=other.id))] == ["SALE_ITEMS_MISMATCH"]


@pytest.mark.asyncio
async def test_ledger_check_parameters_do_not_grow_with_documents(rw):
    """Review finding 4: asyncpg allows 32,767 bind parameters per statement,
    so no statement may carry one parameter per document (a busy branch
    would crash the run): the largest statement must not grow when the
    branch has more sales."""
    from sqlalchemy import event

    async def largest_statement():
        sizes = []

        def count(conn, cursor, statement, parameters, context, executemany):
            sizes.append(len(parameters) if hasattr(parameters, "__len__") else 0)

        engine = rw.db.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            await rc.check_ledger(rw.db, rw.scope())
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return max(sizes)

    for _ in range(3):
        await rw.sale(1)
    await rw.debt_pay(100000)
    few = await largest_statement()
    for _ in range(12):
        await rw.sale(1)
    await rw.debt_pay(300000)
    assert await largest_statement() == few
