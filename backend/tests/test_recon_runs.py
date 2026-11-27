"""On-demand reconciliation runs (stage 3 plan Task 4, brief §20): status
rules, exception upsert by fingerprint, suppression of dismissed findings,
the read-only guarantee and who may run."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text, update

from app.core.business_time import business_date_today
from app.models.daily_closing import DailyClosing
from app.models.reconciliation import ReconciliationException
from app.repositories.sale_repo import sale_repo
from app.services import reconciliation_checks as rc
from tests.conftest import auth_headers, make_user
from tests.test_recon_documents import ReconWorld
from tests.test_recon_period import close_day

D = Decimal


@pytest.fixture
async def rw(db_session, client):
    return await ReconWorld(db_session, client).build()


async def start(rw, user=None, expect=201, **body):
    body.setdefault("scope", "branch")
    if body["scope"] == "branch":
        body.setdefault("branch_id", str(rw.a.id))
    r = await rw.client.post("/api/v1/reconciliation/runs", json=body, headers=auth_headers(user or rw.admin))
    assert r.status_code == expect, r.text
    return r.json()


async def detail(rw, run_id, user=None):
    r = await rw.client.get(f"/api/v1/reconciliation/runs/{run_id}", headers=auth_headers(user or rw.admin))
    assert r.status_code == 200, r.text
    return r.json()


async def mixed_history(rw):
    """Every legitimate flow that touches money, in one branch."""
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "60000"},
                                               {"method": "mobile_money", "amount": "40000", "reference": "MIX1"}])
    await rw.sale(4, payments=[{"method": "cash", "amount": "150000"}])
    p = await rw.debt_pay(100000)
    await rw.reverse(p)
    voided = await rw.sale(2, payments=[{"method": "cash", "amount": "50000"}])
    ob = await rw.old_debt(70000)
    r = await rw.client.post(f"/api/v1/opening-balances/{ob}/cancel", json={"reason": "Imeingizwa mara mbili"},
                             headers=auth_headers(rw.admin))
    assert r.status_code == 200, r.text
    await rw.debt_pay(30000, method="bank_transfer", reference="BK-MIX")
    c = await close_day(rw)
    r = await rw.client.put(f"/api/v1/closings/{c.id}/reopen", json={"reason": "Mauzo yaliyosahaulika"},
                            headers=auth_headers(rw.admin))
    assert r.status_code == 200, r.text
    await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
    await rw.void(voided)
    await close_day(rw)


async def corrupt_closing(rw, delta):
    """Make branch A's closing store total_cash = the real figure + delta."""
    c = (await rw.db.execute(select(DailyClosing).where(DailyClosing.branch_id == rw.a.id))).scalar_one_or_none()
    if c is None:
        await rw.sale(1, customer=False, payments=[{"method": "cash", "amount": "100000"}])
        c = await close_day(rw)
    totals = await sale_repo.get_totals_by_payment_method(rw.db, rw.a.id, *rc.closing_window(c))
    await rw.db.execute(update(DailyClosing).where(DailyClosing.id == c.id)
                        .values(total_cash=D(str(totals["cash"])) + D(delta)))
    await rw.db.flush()
    return c


@pytest.mark.asyncio
async def test_clean_mixed_history_passes(rw):
    await mixed_history(rw)
    run = await start(rw)
    assert (run["status"], run["discrepancy_count"], run["warning_count"]) == ("PASSED", 0, 0)
    assert run["records_examined"] > 0 and run["run_no"].startswith("UPT-")
    assert run["scope"] == "branch" and run["branch_name"] == rw.a.name
    assert {b["branch_id"] for b in run["summary"]["branches"]} == {str(rw.a.id)}
    cust = await start(rw, scope="customer", customer_id=str(rw.customer.id))
    assert (cust["status"], cust["discrepancy_count"]) == ("PASSED", 0)
    assert cust["customer"]["id"] == str(rw.customer.id)


@pytest.mark.asyncio
async def test_failed_run_lists_exceptions(rw):
    await rw.sale(2)
    await rw.db.execute(text(
        "INSERT INTO customer_ledger_entries (id, customer_id, branch_id, entry_type, source_type, source_id,"
        " debit, credit, business_date, description, created_by)"
        " VALUES (:id, :c, :b, 'opening_balance', 'opening_balance', :s, 5000, 0, :d, 'x', :u)"
    ), {"id": uuid.uuid4(), "c": rw.customer.id, "b": rw.a.id, "s": uuid.uuid4(), "d": business_date_today(),
        "u": rw.admin.id})
    await rw.db.flush()
    run = await start(rw)
    assert (run["status"], run["discrepancy_count"]) == ("FAILED", 2)
    assert run["by_code"] == {"LEDGER_BALANCE_MISMATCH": 1, "ORPHAN_LEDGER_ENTRY": 1}
    body = await detail(rw, run["id"])
    [bal] = [e for e in body["exceptions"] if e["code"] == "LEDGER_BALANCE_MISMATCH"]
    assert bal["customer"]["id"] == str(rw.customer.id) and bal["branch_name"] == rw.a.name
    assert (D(bal["expected"]), D(bal["actual"]), D(bal["difference"])) == (D(200000), D(205000), D(5000))
    assert (bal["status"], bal["group"], bal["severity"]) == ("OPEN", "C", "money")
    assert bal["first_run_no"] == bal["last_run_no"] == run["run_no"]


@pytest.mark.asyncio
async def test_warning_only_run(rw):
    await rw.sale(3)
    await rw.debt_pay(50000, method="mobile_money", reference="W1")
    await rw.debt_pay(50000, method="mobile_money", reference="W1")
    run = await start(rw)
    assert (run["status"], run["discrepancy_count"], run["warning_count"]) == ("WARNING", 1, 1)


@pytest.mark.asyncio
async def test_rerun_updates_not_duplicates(rw):
    await corrupt_closing(rw, 1000)
    first = await start(rw)
    await corrupt_closing(rw, 3000)
    second = await start(rw)
    rows = (await rw.db.execute(select(ReconciliationException).where(
        ReconciliationException.branch_id == rw.a.id).execution_options(populate_existing=True))).scalars().all()
    assert len(rows) == 1
    [e] = (await detail(rw, second["id"]))["exceptions"]
    assert (e["first_run_no"], e["last_run_no"], D(e["difference"])) == (first["run_no"], second["run_no"], D(3000))
    assert (await detail(rw, first["id"]))["exceptions"] == []  # its exception moved on to the later run


@pytest.mark.asyncio
async def test_dismissed_suppressed_unless_difference_changes(rw):
    await corrupt_closing(rw, 1000)
    await start(rw)
    await rw.db.execute(update(ReconciliationException).where(ReconciliationException.branch_id == rw.a.id)
                        .values(status="DISMISSED"))
    await rw.db.flush()
    quiet = await start(rw)
    assert (quiet["status"], quiet["discrepancy_count"], quiet["suppressed_count"]) == ("PASSED", 0, 1)
    await corrupt_closing(rw, 2500)
    loud = await start(rw)
    assert (loud["status"], loud["discrepancy_count"], loud["suppressed_count"]) == ("FAILED", 1, 0)
    statuses = sorted((await rw.db.execute(select(ReconciliationException.status).where(
        ReconciliationException.branch_id == rw.a.id))).scalars().all())
    assert statuses == ["DISMISSED", "OPEN"]


FINANCIAL = ("sales", "sale_items", "payments", "payment_allocations", "customer_ledger_entries",
             "opening_balances", "daily_closings", "customers")
AMOUNT = {"sales": "total_amount", "sale_items": "line_total", "payments": "amount",
          "payment_allocations": "amount", "customer_ledger_entries": "debit - credit",
          "opening_balances": "amount", "daily_closings": "total_cash", "customers": "credit_limit"}


async def snapshot(db):
    out = {}
    for t in FINANCIAL:
        out[t] = tuple((await db.execute(text(
            f"SELECT count(*), coalesce(sum({AMOUNT[t]}),0), md5(coalesce(string_agg(t::text, '|' ORDER BY id), ''))"
            f" FROM {t} t"))).one())
    return out


@pytest.mark.asyncio
async def test_run_writes_no_financial_rows(rw):
    await mixed_history(rw)
    await corrupt_closing(rw, 700)
    before = await snapshot(rw.db)
    run = await start(rw)
    await start(rw, scope="all")
    assert run["status"] == "FAILED"
    assert await snapshot(rw.db) == before


@pytest.mark.asyncio
async def test_scope_validation(rw):
    r = await start(rw, scope="sale", expect=422)
    assert r["code"] == "RECON_SCOPE_INVALID"
    r = await start(rw, scope="branch", branch_id=str(uuid.uuid4()), expect=422)
    assert r["code"] == "RECON_SCOPE_INVALID"
    r = await start(rw, period="custom", from_date="2026-11-20", to_date="2026-11-10", expect=422)
    assert r["code"] == "DATE_RANGE_INVALID"


@pytest.mark.asyncio
async def test_unauthorized_reconciliation(rw):
    keeper = await make_user(rw.db, "store_keeper")
    for user in (rw.cashier_a, keeper):
        await start(rw, user=user, expect=403)
        for path in ("/api/v1/reconciliation/runs", f"/api/v1/reconciliation/runs/{uuid.uuid4()}"):
            r = await rw.client.get(path, headers=auth_headers(user))
            assert r.status_code == 403, (path, r.text)
    gm = await make_user(rw.db, "general_manager")
    run = await start(rw, user=gm)
    r = await rw.client.get("/api/v1/reconciliation/runs", headers=auth_headers(gm))
    assert r.status_code == 200 and run["id"] in [x["id"] for x in r.json()]
    assert (await detail(rw, run["id"], user=gm))["run_by_name"]


@pytest.mark.asyncio
async def test_dismissed_duplicate_reference_reopens_on_new_reuse(rw):
    """Review finding 3: dismissing a reused M-Pesa code must not hide a
    later, third use of the same code."""
    await rw.sale(5)
    await rw.debt_pay(50000, method="mobile_money", reference="DUPX")
    await rw.debt_pay(50000, method="mobile_money", reference="DUPX")
    await start(rw)
    await rw.db.execute(update(ReconciliationException).where(ReconciliationException.branch_id == rw.a.id)
                        .values(status="DISMISSED"))
    await rw.db.flush()
    assert (await start(rw))["suppressed_count"] == 1
    await rw.debt_pay(50000, method="mobile_money", reference="DUPX")
    run = await start(rw)
    assert (run["status"], run["warning_count"], run["suppressed_count"]) == ("WARNING", 1, 0)
