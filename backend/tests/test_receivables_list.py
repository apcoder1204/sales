"""Madeni Yote: every open debt (credit sales and approved old debts) in one
list, scoped by branch like the rest of the debt features."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.business_time import business_date_today
from tests.conftest import auth_headers, make_customer, make_user
from tests.test_debt_payments import World


class Debts(World):
    async def build(self):
        await super().build()
        db = self.db
        self.manager = await make_user(db, "general_manager")
        self.keeper = await make_user(db, "store_keeper")
        self.customer.name = "Alpha Electric"
        self.juma = await make_customer(db, name="Juma Hardware", credit_limit=Decimal("1000000"))
        await db.flush()
        # A: 2 items on credit (200k, due in 30 days) and a 1-item sale paid off
        self.open_sale = await self.credit_sale(self.a, self.cashier_a, 2, due_in_days=30)
        self.paid_sale = await self.credit_sale(self.a, self.cashier_a, 1, due_in_days=30)
        r = await self.pay(self.cashier_a, {"method": "cash", "amount": "100000",
                                            "allocations": [{"sale_id": str(self.paid_sale), "amount": "100000"}]})
        assert r.status_code == 201, r.text
        # B: Juma's approved old debt (overdue) and a pending one (not owed yet)
        self.old = await self.old_debt(self.b, "300000", "Daftari uk. 14", approve=True)
        self.pending = await self.old_debt(self.b, "50000", "Daftari uk. 15", approve=False)
        return self

    async def old_debt(self, branch, amount, ref, approve):
        r = await self.client.post(f"/api/v1/customers/{self.juma.id}/opening-balances", json={
            "branch_id": str(branch.id), "amount": amount, "reference": ref,
            "effective_date": (business_date_today() - timedelta(days=60)).isoformat(),
        }, headers=auth_headers(self.admin))
        assert r.status_code == 201, r.text
        if approve:
            a = await self.client.post(f"/api/v1/opening-balances/{r.json()['id']}/approve",
                                       json={}, headers=auth_headers(self.admin))
            assert a.status_code == 200, a.text
        return r.json()["id"]

    async def list(self, user, **params):
        r = await self.client.get("/api/v1/receivables", params=params, headers=auth_headers(user))
        assert r.status_code == 200, r.text
        return r.json()

    def mine(self, body):
        """Only this test's rows (the dev DB may hold other customers)."""
        ours = {str(self.customer.id), str(self.juma.id)}
        return {x["id"]: x for x in body["items"] if x["customer"]["id"] in ours}


@pytest.fixture
async def d(db_session, client):
    return await Debts(db_session, client).build()


@pytest.mark.asyncio
async def test_admin_sees_open_debts_of_every_branch(d):
    rows = d.mine(await d.list(d.admin))
    assert set(rows) == {str(d.open_sale), d.old}
    sale = rows[str(d.open_sale)]
    assert sale["kind"] == "sale" and sale["branch_id"] == str(d.a.id)
    assert sale["customer"]["name"] == "Alpha Electric"
    assert (sale["amount"], sale["paid"], sale["outstanding"], sale["status"]) == (
        "200000.00", "0.00", "200000.00", "UNPAID")
    old = rows[d.old]
    assert old["kind"] == "opening_balance" and old["status"] == "OVERDUE"
    assert old["customer"]["name"] == "Juma Hardware"
    assert old["outstanding"] == "300000.00"


@pytest.mark.asyncio
async def test_branch_filter_and_summary(d):
    body = await d.list(d.admin, branch_id=str(d.b.id))
    assert set(d.mine(body)) == {d.old}
    assert all(x["branch_id"] == str(d.b.id) for x in body["items"])
    s = body["summary"]
    assert Decimal(s["total_outstanding"]) == sum(Decimal(x["outstanding"]) for x in body["items"])
    assert Decimal(s["overdue"]) >= Decimal("300000")
    assert s["customers_owing"] >= 1
    assert body["total"] == len(body["items"])


@pytest.mark.asyncio
async def test_cashier_sees_only_own_branch(d):
    body = await d.list(d.cashier_a, branch_id=str(d.b.id))  # asking for B is ignored
    assert set(d.mine(body)) == {str(d.open_sale)}
    assert all(x["branch_id"] == str(d.a.id) for x in body["items"])
    assert set(d.mine(await d.list(d.cashier_b))) == {d.old}


@pytest.mark.asyncio
async def test_manager_sees_all_storekeeper_refused(d):
    assert set(d.mine(await d.list(d.manager))) == {str(d.open_sale), d.old}
    r = await d.client.get("/api/v1/receivables", headers=auth_headers(d.keeper))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_status_and_search_filters(d):
    assert set(d.mine(await d.list(d.admin, status="OVERDUE"))) == {d.old}
    assert set(d.mine(await d.list(d.admin, status="PAID"))) == {str(d.paid_sale)}
    assert set(d.mine(await d.list(d.admin, q="juma"))) == {d.old}
    assert set(d.mine(await d.list(d.admin, q=d.juma.customer_no))) == {d.old}


@pytest.mark.asyncio
async def test_pagination(d):
    body = await d.list(d.admin, q="Alpha Electric", status="ALL", per_page=1, page=1)
    assert len(body["items"]) == 1 and body["total"] == 2
    page2 = await d.list(d.admin, q="Alpha Electric", status="ALL", per_page=1, page=2)
    assert {body["items"][0]["id"], page2["items"][0]["id"]} == {str(d.open_sale), str(d.paid_sale)}
