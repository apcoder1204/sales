"""Collection follow-up notes (brief §16): who was contacted, how, what they
promised — and never a change to what anyone owes."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.business_time import business_date_today
from app.db import seed_demo
from app.models.customer_ledger import CustomerLedgerEntry
from app.models.follow_up import CustomerFollowUp
from app.models.payment import Payment
from app.services import ledger_service
from tests.conftest import auth_headers, make_user
from tests.test_debt_payments import World


@pytest.fixture
async def w(db_session, client):
    return await World(db_session, client).build()


def body(**over):
    b = {"contact_date": business_date_today().isoformat(), "method": "phone",
         "note": "Amesema atalipa Ijumaa", "expected_payment_date": (business_date_today() + timedelta(days=3)).isoformat()}
    b.update(over)
    return b


async def add(w, user, **over):
    return await w.client.post(f"/api/v1/customers/{w.customer.id}/follow-ups", json=body(**over),
                               headers=auth_headers(user))


async def listed(w, user, **params):
    r = await w.client.get(f"/api/v1/customers/{w.customer.id}/follow-ups", params=params, headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_cashier_adds_follow_up_own_branch(w):
    r = await add(w, w.cashier_a)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["branch_id"] == str(w.a.id) and out["branch_name"] == w.a.name
    assert out["method"] == "phone" and out["note"] == "Amesema atalipa Ijumaa"
    assert out["responsible_user_name"] == w.cashier_a.full_name
    assert (await add(w, w.cashier_a, branch_id=str(w.b.id))).status_code == 403


@pytest.mark.asyncio
async def test_admin_must_choose_branch(w):
    r = await add(w, w.admin)
    assert r.status_code == 400 and r.json()["code"] == "BRANCH_REQUIRED"
    assert (await add(w, w.admin, branch_id=str(w.b.id))).status_code == 201


@pytest.mark.asyncio
async def test_follow_up_changes_no_balance(w):
    await w.credit_sale(w.a, w.cashier_a, 2)

    async def snapshot():
        n_ledger = (await w.db.execute(select(func.count()).select_from(CustomerLedgerEntry).where(
            CustomerLedgerEntry.customer_id == w.customer.id))).scalar()
        n_pay = (await w.db.execute(select(func.count()).select_from(Payment).where(
            Payment.customer_id == w.customer.id))).scalar()
        return n_ledger, n_pay, await ledger_service.customer_balance(w.db, w.customer.id)

    before = await snapshot()
    assert (await add(w, w.cashier_a)).status_code == 201
    assert await snapshot() == before
    assert before[2] == Decimal("200000")


@pytest.mark.asyncio
async def test_cashier_lists_only_own_branch_follow_ups(w):
    await add(w, w.cashier_a, note="Tawi A")
    await add(w, w.cashier_b, note="Tawi B")
    assert [x["note"] for x in await listed(w, w.cashier_b, branch_id=str(w.a.id))] == ["Tawi B"]
    assert {x["note"] for x in await listed(w, w.admin)} == {"Tawi A", "Tawi B"}
    manager = await make_user(w.db, "general_manager")
    assert len(await listed(w, manager)) == 2


@pytest.mark.asyncio
async def test_manager_cannot_add(w):
    manager = await make_user(w.db, "general_manager")
    assert (await add(w, manager, branch_id=str(w.a.id))).status_code == 403


@pytest.mark.asyncio
async def test_bad_input_422(w):
    tomorrow = (business_date_today() + timedelta(days=1)).isoformat()
    assert (await add(w, w.cashier_a, contact_date=tomorrow)).status_code == 422
    assert (await add(w, w.cashier_a, method="email")).status_code == 422
    assert (await add(w, w.cashier_a, note="ok")).status_code == 422


@pytest.mark.asyncio
async def test_list_newest_first(w):
    await add(w, w.cashier_a, note="Zamani", contact_date=(business_date_today() - timedelta(days=5)).isoformat())
    await add(w, w.cashier_a, note="Leo")
    assert [x["note"] for x in await listed(w, w.cashier_a)] == ["Leo", "Zamani"]


@pytest.mark.asyncio
async def test_demo_wipe_clears_follow_ups(w, db_session):
    from app.models.stock_request import StockRequest  # noqa: F401  (wipe handles them since 9e93ca3)
    assert (await add(w, w.cashier_a)).status_code == 201
    await seed_demo._wipe_generated_data(db_session, commit=False)
    n = (await db_session.execute(select(func.count()).select_from(CustomerFollowUp))).scalar()
    assert n == 0
