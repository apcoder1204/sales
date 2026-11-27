"""Debt reports (brief §29 items 1–7, 9): branch-scoped, Tanzania business
dates, and totals that agree with the ledger."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.business_time import business_date_today
from app.models.customer_ledger import CustomerLedgerEntry
from app.services.whatsapp_service import REPORT_TYPE_ROLES
from tests.conftest import auth_headers, make_customer, make_user
from tests.test_debt_payments import World

D = Decimal


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


async def report(w, user, path, expect=200, **params):
    r = await w.client.get(f"/api/v1/reports/debts/{path}", params={k: str(v) for k, v in params.items()},
                           headers=auth_headers(user))
    assert r.status_code == expect, r.text
    return r.json()


def mine(w, rows, key="customer"):
    return [x for x in rows if x[key]["id"] == str(w.customer.id)]


@pytest.mark.asyncio
async def test_outstanding_report(w):
    await w.credit_sale(w.a, w.cashier_a, 2, due_in_days=-5)
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=5)
    body = await report(w, w.admin, "outstanding", branch_id=w.a.id)
    [row] = mine(w, body["rows"])
    assert (D(row["balance"]), D(row["overdue"]), D(row["credit_limit"])) == (D(300000), D(200000), D(5000000))
    assert row["flags"] == ["OVERDUE"]
    assert D(body["summary"]["total_balance"]) == sum(D(x["balance"]) for x in body["rows"])
    assert body["summary"]["customers"] == len(body["rows"])


@pytest.mark.asyncio
async def test_overdue_report_days(w):
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=-12)
    await w.credit_sale(w.a, w.cashier_a, 1, due_in_days=3)
    body = await report(w, w.admin, "overdue", branch_id=w.a.id)
    rows = mine(w, body["rows"])
    assert [(r["days_overdue"], D(r["outstanding"])) for r in rows] == [(12, D(100000))]
    assert body["summary"]["count"] == len(body["rows"])


@pytest.mark.asyncio
async def test_collections_excludes_reversed_and_sale_payments(w):
    r = await w.client.post("/api/v1/sales", json={
        "branch_id": str(w.a.id), "customer_id": str(w.customer.id),
        "payments": [{"method": "cash", "amount": "100000"}],
        "items": [{"product_id": str(w.product.id), "quantity": 3}],
    }, headers=auth_headers(w.cashier_a))
    assert r.status_code == 201, r.text
    p1 = await w.pay(w.cashier_a, {"method": "mobile_money", "amount": "50000", "reference": "MP1"})
    p2 = await w.pay(w.cashier_a, {"method": "cash", "amount": "30000"})
    rv = await w.client.post(f"/api/v1/payments/{p2.json()['id']}/reverse", json={"reason": "Kimakosa kabisa"},
                             headers=auth_headers(w.admin))
    assert rv.status_code == 200, rv.text
    body = await report(w, w.admin, "collections", branch_id=w.a.id, period="today")
    assert [x["payment_no"] for x in body["rows"]] == [p1.json()["payment_no"]]
    assert D(body["summary"]["total"]) == D(50000) and body["summary"]["count"] == 1
    assert D(body["summary"]["by_method"]["mobile_money"]) == D(50000)
    assert D(body["summary"]["by_method"]["cash"]) == 0


@pytest.mark.asyncio
async def test_branches_report_two_branches(w):
    await w.credit_sale(w.a, w.cashier_a, 2, due_in_days=-1)
    await w.credit_sale(w.b, w.cashier_b, 1, due_in_days=10)
    await w.pay(w.cashier_b, {"method": "cash", "amount": "40000"})
    body = await report(w, w.admin, "branches", period="today")
    rows = {x["branch_name"]: x for x in body["rows"]}
    assert (D(rows[w.a.name]["outstanding"]), D(rows[w.a.name]["overdue"])) == (D(200000), D(200000))
    assert (D(rows[w.b.name]["outstanding"]), D(rows[w.b.name]["collected_in_period"])) == (D(60000), D(40000))
    assert D(body["summary"]["outstanding"]) == sum(D(x["outstanding"]) for x in body["rows"])


@pytest.mark.asyncio
async def test_credit_utilization_admin_only(w):
    await w.credit_sale(w.a, w.cashier_a, 2)
    await w.credit_sale(w.b, w.cashier_b, 2)
    body = await report(w, w.admin, "credit-utilization")
    [row] = mine(w, body["rows"])
    assert (D(row["balance"]), D(row["used_pct"]), D(row["available"])) == (D(400000), D("8.00"), D(4600000))
    await report(w, w.cashier_a, "credit-utilization", expect=403)
    manager = await make_user(w.db, "general_manager")
    await report(w, manager, "credit-utilization")


@pytest.mark.asyncio
async def test_opening_balance_report_by_status(w):
    async def enter(amount, ref):
        r = await w.client.post(f"/api/v1/customers/{w.customer.id}/opening-balances", json={
            "branch_id": str(w.a.id), "amount": amount, "reference": ref,
            "effective_date": business_date_today().isoformat()}, headers=auth_headers(w.admin))
        assert r.status_code == 201, r.text
        return r.json()["id"]
    a = await enter("100000", f"R1-{uuid.uuid4().hex[:4]}")
    b = await enter("40000", f"R2-{uuid.uuid4().hex[:4]}")
    await enter("25000", f"R3-{uuid.uuid4().hex[:4]}")
    await w.client.post(f"/api/v1/opening-balances/{a}/approve", json={}, headers=auth_headers(w.admin))
    await w.client.post(f"/api/v1/opening-balances/{b}/reject", json={"note": "Si sahihi"}, headers=auth_headers(w.admin))
    body = await report(w, w.admin, "opening-balances", branch_id=w.a.id)
    s = body["summary"]
    assert (s["approved"]["count"], D(s["approved"]["amount"])) == (1, D(100000))
    assert (s["rejected"]["count"], D(s["rejected"]["amount"])) == (1, D(40000))
    assert (s["pending"]["count"], D(s["pending"]["amount"])) == (1, D(25000))
    only = await report(w, w.admin, "opening-balances", branch_id=w.a.id, status="approved")
    assert [x["status"] for x in only["rows"]] == ["approved"]
    await report(w, await make_user(w.db, "general_manager"), "opening-balances", expect=403)


@pytest.mark.asyncio
async def test_cashier_reports_forced_to_own_branch(w):
    await w.credit_sale(w.a, w.cashier_a, 2, due_in_days=-3)
    await w.credit_sale(w.b, w.cashier_b, 1, due_in_days=-3)
    for path in ("outstanding", "overdue"):
        body = await report(w, w.cashier_b, path, branch_id=w.a.id)
        [row] = mine(w, body["rows"])
        assert D(row.get("balance", row.get("outstanding"))) == D(100000)
    br = await report(w, w.cashier_b, "branches", branch_id=w.a.id, period="today")
    assert [x["branch_name"] for x in br["rows"]] == [w.b.name]
    ag = await report(w, w.cashier_b, "ageing", branch_id=w.a.id)
    assert [x["branch_name"] for x in ag["by_branch"]] == [w.b.name]
    keeper = await make_user(w.db, "store_keeper")
    await report(w, keeper, "outstanding", expect=403)


@pytest.mark.asyncio
async def test_report_totals_reconcile_with_ledger(w):
    other = await make_customer(w.db, credit_limit=D("5000000"))
    await w.credit_sale(w.a, w.cashier_a, 3, due_in_days=-2)
    await w.pay(w.cashier_a, {"method": "cash", "amount": "70000"})
    keep, w.customer = w.customer, other
    await w.credit_sale(w.a, w.cashier_a, 2)
    w.customer = keep
    out = await report(w, w.admin, "outstanding", branch_id=w.a.id)
    listed = (await w.client.get("/api/v1/receivables", params={"branch_id": str(w.a.id)},
                                 headers=auth_headers(w.admin))).json()
    ledger = (await w.db.execute(select(func.sum(CustomerLedgerEntry.debit - CustomerLedgerEntry.credit))
                                 .where(CustomerLedgerEntry.branch_id == w.a.id))).scalar()
    assert D(out["summary"]["total_balance"]) == D(listed["summary"]["total_outstanding"]) == D(ledger) == D(430000)
    ageing = await report(w, w.admin, "ageing", branch_id=w.a.id)
    assert D(ageing["total"]) == D(430000)


def test_whatsapp_accepts_debt_report_types():
    assert set(REPORT_TYPE_ROLES["debt_reconciliation"]) == {"super_admin", "admin", "general_manager"}
    for t in ("debt_outstanding", "debt_overdue", "debt_ageing", "debt_collections", "debt_branches",
              "customer_statement"):
        assert set(REPORT_TYPE_ROLES[t]) == {"super_admin", "admin", "general_manager", "cashier"}
    assert set(REPORT_TYPE_ROLES["debt_credit_utilization"]) == {"super_admin", "admin", "general_manager"}
    assert set(REPORT_TYPE_ROLES["debt_opening_balances"]) == {"super_admin", "admin", "cashier"}


@pytest.mark.asyncio
async def test_reconciliation_report(db_session, client):
    from sqlalchemy import update as sa_update

    from app.models.reconciliation import ReconciliationException
    from tests.test_recon_documents import ReconWorld
    from tests.test_recon_runs import corrupt_closing, start

    rw = await ReconWorld(db_session, client).build()
    await rw.sale(3)
    await rw.debt_pay(50000, method="mobile_money", reference="RPT1")
    await rw.debt_pay(50000, method="mobile_money", reference="RPT1")
    await corrupt_closing(rw, 1000)
    run = await start(rw)
    await db_session.execute(sa_update(ReconciliationException).where(
        ReconciliationException.code == "DUPLICATE_PAYMENT_REFERENCE",
        ReconciliationException.branch_id == rw.a.id).values(status="DISMISSED"))
    await db_session.flush()

    body = await report(rw, rw.admin, "reconciliation", branch_id=rw.a.id)
    assert [x["code"] for x in body["rows"]] == ["CLOSING_TOTAL_MISMATCH"]
    assert body["summary"]["last_run"]["run_no"] == run["run_no"]
    assert body["summary"]["by_status"]["DISMISSED"] == 1 and body["summary"]["money_open"] == 1
    every = await report(rw, rw.admin, "reconciliation", branch_id=rw.a.id, status="all")
    assert sorted(x["code"] for x in every["rows"]) == ["CLOSING_TOTAL_MISMATCH", "DUPLICATE_PAYMENT_REFERENCE"]
    await report(rw, await make_user(db_session, "general_manager"), "reconciliation")
    await report(rw, rw.cashier_a, "reconciliation", expect=403)
