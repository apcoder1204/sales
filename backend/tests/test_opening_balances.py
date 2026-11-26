"""Old debts (Madeni ya Zamani): the admin or a cashier (own branch) enters
one; the single admin checks and approves it as a separate step, and can
cancel an approved one while nothing is paid on it."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.business_time import business_date_today
from app.models.customer_ledger import CustomerLedgerEntry
from app.services import ledger_service
from tests.conftest import auth_headers, get_main_store, make_branch, make_customer, make_user


class Ctx:
    async def build(self, db, client):
        self.db, self.client = db, client
        self.branch = await make_branch(db)
        self.other = await make_branch(db)
        self.admin = await make_user(db, "admin")
        self.cashier = await make_user(db, "cashier", branch=self.branch)
        self.other_cashier = await make_user(db, "cashier", branch=self.other)
        self.manager = await make_user(db, "general_manager")
        self.customer = await make_customer(db, credit_days=30)
        return self

    async def enter(self, user=None, **over):
        body = {
            "branch_id": str(self.branch.id), "amount": "350000",
            "effective_date": (business_date_today() - timedelta(days=60)).isoformat(),
            "reference": "Daftari uk. 12", "description": "Deni la mwaka jana",
        }
        body.update(over)
        return await self.client.post(
            f"/api/v1/customers/{self.customer.id}/opening-balances", json=body,
            headers=auth_headers(user or self.admin),
        )

    async def decide(self, ob_id, action, user, note=None):
        body = {"note": note} if note is not None else {}
        if action == "cancel":
            body = {"reason": note} if note is not None else {}
        return await self.client.post(f"/api/v1/opening-balances/{ob_id}/{action}", json=body,
                                      headers=auth_headers(user))


@pytest.fixture
async def c(db_session, client):
    return await Ctx().build(db_session, client)


@pytest.mark.asyncio
async def test_pending_old_debt_is_not_owed(c):
    r = await c.enter()
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    assert r.json()["due_date"] == (business_date_today() - timedelta(days=30)).isoformat()
    assert await ledger_service.customer_balance(c.db, c.customer.id) == Decimal("0")
    assert await ledger_service.receivables(c.db, c.customer.id) == []
    listed = await c.client.get("/api/v1/opening-balances", params={"status": "pending"},
                                headers=auth_headers(c.admin))
    assert r.json()["id"] in [x["id"] for x in listed.json()]


@pytest.mark.asyncio
async def test_admin_approves_own_entry_as_separate_step(c):
    ob = (await c.enter()).json()
    assert ob["status"] == "pending"
    r = await c.decide(ob["id"], "approve", c.admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert await ledger_service.customer_balance(c.db, c.customer.id) == Decimal("350000")
    rows = await ledger_service.receivables(c.db, c.customer.id)
    assert len(rows) == 1
    assert rows[0].reference.startswith("DENI-ZAMANI")
    assert rows[0].status == "OVERDUE"
    entry = (await c.db.execute(select(CustomerLedgerEntry).where(
        CustomerLedgerEntry.customer_id == c.customer.id))).scalar_one()
    assert entry.entry_type == "opening_balance"
    assert entry.business_date == business_date_today() - timedelta(days=60)


@pytest.mark.asyncio
async def test_duplicate_old_debt_rejected(c):
    assert (await c.enter()).status_code == 201
    r = await c.enter()
    assert r.status_code == 409
    assert r.json()["code"] == "OPENING_BALANCE_DUPLICATE"


@pytest.mark.asyncio
async def test_reject_writes_no_ledger(c):
    ob = (await c.enter()).json()
    assert (await c.decide(ob["id"], "reject", c.admin)).status_code == 422  # note required
    r = await c.decide(ob["id"], "reject", c.admin, note="Haijathibitishwa")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    n = (await c.db.execute(select(func.count()).select_from(CustomerLedgerEntry).where(
        CustomerLedgerEntry.customer_id == c.customer.id))).scalar()
    assert n == 0
    again = await c.decide(ob["id"], "approve", c.admin)
    assert again.status_code == 400
    assert again.json()["code"] == "OPENING_BALANCE_NOT_PENDING"
    assert (await c.enter()).status_code == 201  # a rejected entry doesn't block re-entry


@pytest.mark.asyncio
async def test_pay_old_debt(c):
    ob = (await c.enter()).json()
    await c.decide(ob["id"], "approve", c.admin)
    r = await c.client.post(f"/api/v1/customers/{c.customer.id}/payments", json={
        "method": "cash", "amount": "350000",
        "allocations": [{"opening_balance_id": ob["id"], "amount": "350000"}],
    }, headers=auth_headers(c.cashier))
    assert r.status_code == 201, r.text
    assert r.json()["allocations"][0]["reference"].startswith("DENI-ZAMANI")
    assert await ledger_service.receivables(c.db, c.customer.id) == []
    assert await ledger_service.customer_balance(c.db, c.customer.id) == Decimal("0")


@pytest.mark.asyncio
async def test_cashier_enters_old_debt_for_own_branch(c):
    r = await c.enter(user=c.cashier, branch_id=None)
    assert r.status_code == 201, r.text
    assert r.json()["branch_id"] == str(c.branch.id)
    assert r.json()["status"] == "pending"
    assert r.json()["entered_by"] == str(c.cashier.id)
    # Still owes nothing until the admin approves it
    assert await ledger_service.customer_balance(c.db, c.customer.id) == Decimal("0")
    r = await c.decide(r.json()["id"], "approve", c.admin)
    assert r.status_code == 200, r.text
    assert await ledger_service.customer_balance(c.db, c.customer.id, c.branch.id) == Decimal("350000")


@pytest.mark.asyncio
async def test_cashier_cannot_enter_for_another_branch(c):
    r = await c.enter(user=c.cashier, branch_id=str(c.other.id))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_must_choose_branch(c):
    r = await c.enter(branch_id=None)
    assert r.status_code == 400
    assert r.json()["code"] == "BRANCH_REQUIRED"


@pytest.mark.asyncio
async def test_manager_cannot_enter_old_debt(c):
    assert (await c.enter(user=c.manager)).status_code == 403


@pytest.mark.asyncio
async def test_cashier_cannot_decide_or_cancel(c):
    ob = (await c.enter(user=c.cashier, branch_id=None)).json()
    assert (await c.decide(ob["id"], "approve", c.cashier)).status_code == 403
    assert (await c.decide(ob["id"], "reject", c.cashier, note="Si sahihi")).status_code == 403
    await c.decide(ob["id"], "approve", c.admin)
    assert (await c.decide(ob["id"], "cancel", c.cashier, note="Si sahihi")).status_code == 403


@pytest.mark.asyncio
async def test_cashier_lists_only_own_branch(c):
    mine = (await c.enter(user=c.cashier, branch_id=None)).json()
    theirs = (await c.enter(branch_id=str(c.other.id))).json()
    r = await c.client.get("/api/v1/opening-balances", headers=auth_headers(c.cashier))
    assert r.status_code == 200, r.text
    ids = {x["id"] for x in r.json()}
    assert mine["id"] in ids and theirs["id"] not in ids
    r = await c.client.get("/api/v1/opening-balances", params={"branch_id": str(c.other.id)},
                           headers=auth_headers(c.cashier))
    assert theirs["id"] not in {x["id"] for x in r.json()}
    r = await c.client.get("/api/v1/opening-balances", headers=auth_headers(c.admin))
    assert {mine["id"], theirs["id"]} <= {x["id"] for x in r.json()}


@pytest.mark.asyncio
async def test_cancel_approved_old_debt(c):
    ob = (await c.enter()).json()
    await c.decide(ob["id"], "approve", c.admin)
    assert (await c.decide(ob["id"], "cancel", c.admin)).status_code == 422  # reason required
    r = await c.decide(ob["id"], "cancel", c.admin, note="Kiasi si sahihi")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "Kiasi si sahihi"
    assert body["cancelled_by_name"] == c.admin.full_name
    assert await ledger_service.customer_balance(c.db, c.customer.id) == Decimal("0")
    assert await ledger_service.receivables(c.db, c.customer.id) == []
    entries = (await c.db.execute(select(CustomerLedgerEntry).where(
        CustomerLedgerEntry.customer_id == c.customer.id))).scalars().all()
    assert sorted((e.entry_type, e.debit, e.credit) for e in entries) == [
        ("opening_balance", Decimal("350000.00"), Decimal("0.00")),
        ("opening_void", Decimal("0.00"), Decimal("350000.00")),
    ]
    again = await c.decide(ob["id"], "cancel", c.admin, note="Tena")
    assert again.status_code == 400
    assert again.json()["code"] == "OPENING_BALANCE_NOT_APPROVED"
    assert (await c.enter()).status_code == 201  # a cancelled entry doesn't block re-entry


@pytest.mark.asyncio
async def test_cancel_pending_old_debt_refused(c):
    ob = (await c.enter()).json()
    r = await c.decide(ob["id"], "cancel", c.admin, note="Si sahihi")
    assert r.status_code == 400
    assert r.json()["code"] == "OPENING_BALANCE_NOT_APPROVED"


@pytest.mark.asyncio
async def test_cancel_blocked_while_payment_active(c):
    ob = (await c.enter()).json()
    await c.decide(ob["id"], "approve", c.admin)
    pay = await c.client.post(f"/api/v1/customers/{c.customer.id}/payments",
                              json={"method": "cash", "amount": "100000"}, headers=auth_headers(c.cashier))
    assert pay.status_code == 201, pay.text
    r = await c.decide(ob["id"], "cancel", c.admin, note="Si sahihi")
    assert r.status_code == 400
    assert r.json()["code"] == "OPENING_BALANCE_HAS_PAYMENTS"
    rv = await c.client.post(f"/api/v1/payments/{pay.json()['id']}/reverse",
                             json={"reason": "Imerekodiwa kimakosa"}, headers=auth_headers(c.admin))
    assert rv.status_code == 200, rv.text
    r = await c.decide(ob["id"], "cancel", c.admin, note="Si sahihi")
    assert r.status_code == 200, r.text
    assert await ledger_service.customer_balance(c.db, c.customer.id) == Decimal("0")


@pytest.mark.asyncio
async def test_future_effective_date_rejected(c):
    r = await c.enter(effective_date=(business_date_today() + timedelta(days=1)).isoformat())
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_old_debt_needs_pos_branch(c):
    store = await get_main_store(c.db)
    r = await c.enter(branch_id=str(store.id))
    assert r.status_code == 400
