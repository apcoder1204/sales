"""Exception management (stage 3 plan Task 5, brief §21): review, resolve
and dismiss with a reason and a supporting reference; resolving is refused
while the discrepancy is still there; final states are locked; only admins
change a status."""
import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import auth_headers, make_user
from tests.test_recon_documents import ReconWorld
from tests.test_recon_period import close_day
from tests.test_recon_runs import corrupt_closing, start


@pytest.fixture
async def rw(db_session, client):
    return await ReconWorld(db_session, client).build()


async def live(rw, user=None, **params):
    r = await rw.client.get("/api/v1/reconciliation/exceptions", params={"branch_id": str(rw.a.id), **params},
                            headers=auth_headers(user or rw.admin))
    assert r.status_code == 200, r.text
    return r.json()


async def change(rw, exc_id, status, reason="Nimeangalia daftari", reference=None, user=None, expect=200):
    body = {"status": status, "reason": reason}
    if reference is not None:
        body["reference"] = reference
    r = await rw.client.post(f"/api/v1/reconciliation/exceptions/{exc_id}/status", json=body,
                             headers=auth_headers(user or rw.admin))
    assert r.status_code == expect, r.text
    return r.json()


async def one_exception(rw, delta=1000):
    await corrupt_closing(rw, delta)
    await start(rw)
    [e] = await live(rw)
    return e


@pytest.mark.asyncio
async def test_status_flow(rw):
    e = await one_exception(rw)
    assert e["code"] == "CLOSING_TOTAL_MISMATCH" and e["closing"]["register_number"] == 1
    reviewed = await change(rw, e["id"], "UNDER_REVIEW")
    assert (reviewed["status"], reviewed["status_reason"], reviewed["status_by_name"]) == (
        "UNDER_REVIEW", "Nimeangalia daftari", rw.admin.full_name)
    done = await change(rw, e["id"], "DISMISSED", reason="Hesabu ya zamani, imekubaliwa", reference="Barua 12/11")
    assert (done["status"], done["status_reference"]) == ("DISMISSED", "Barua 12/11")
    assert await live(rw) == []
    assert [x["id"] for x in await live(rw, status="all")] == [e["id"]]
    audits = (await rw.db.execute(select(AuditLog).where(
        AuditLog.action == "RECON_EXCEPTION_STATUS", AuditLog.entity_id == e["id"]))).scalars().all()
    assert sorted((a.details["from"], a.details["to"]) for a in audits) == [
        ("OPEN", "UNDER_REVIEW"), ("UNDER_REVIEW", "DISMISSED")]


@pytest.mark.asyncio
async def test_resolve_requires_reference_and_reason(rw):
    e = await one_exception(rw)
    await change(rw, e["id"], "RESOLVED", reason="  ", reference="X1", expect=422)
    r = await change(rw, e["id"], "RESOLVED", reason="Imerekebishwa", expect=422)
    assert r["code"] == "EXCEPTION_REFERENCE_REQUIRED"
    r = await change(rw, e["id"], "DISMISSED", reason="Imerekebishwa", reference="   ", expect=422)
    assert r["code"] == "EXCEPTION_REFERENCE_REQUIRED"


@pytest.mark.asyncio
async def test_resolve_refused_while_present(rw):
    e = await one_exception(rw)
    r = await change(rw, e["id"], "RESOLVED", reason="Nimerekebisha", reference="Ufungaji upya", expect=409)
    assert r["code"] == "EXCEPTION_STILL_PRESENT"
    [still] = await live(rw)
    assert still["status"] == "OPEN"
    # The normal correcting action: reopen the day and close it again, which
    # recomputes its totals from the payments.
    closing_id = (await rw.client.get("/api/v1/closings", params={"branch_id": str(rw.a.id)},
                                      headers=auth_headers(rw.admin))).json()
    closing_id = (closing_id["items"] if isinstance(closing_id, dict) else closing_id)[0]["id"]
    r = await rw.client.put(f"/api/v1/closings/{closing_id}/reopen", json={"reason": "Kurekebisha jumla"},
                            headers=auth_headers(rw.admin))
    assert r.status_code == 200, r.text
    await close_day(rw)
    done = await change(rw, e["id"], "RESOLVED", reason="Siku imefungwa upya", reference=e["closing"]["business_date"])
    assert done["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_final_states_locked(rw):
    e = await one_exception(rw)
    await change(rw, e["id"], "DISMISSED", reference="R-1")
    r = await change(rw, e["id"], "UNDER_REVIEW", expect=422)
    assert r["code"] == "EXCEPTION_CLOSED"
    await corrupt_closing(rw, 4000)  # a new difference: a new OPEN exception
    await start(rw)
    [fresh] = await live(rw)
    r = await change(rw, fresh["id"], "OPEN", expect=422)
    assert r["code"] == "EXCEPTION_TRANSITION_INVALID"


@pytest.mark.asyncio
async def test_unauthorized_exception_resolution(rw):
    e = await one_exception(rw)
    gm = await make_user(rw.db, "general_manager")
    keeper = await make_user(rw.db, "store_keeper")
    for user in (gm, rw.cashier_a, keeper):
        await change(rw, e["id"], "DISMISSED", reference="R", user=user, expect=403)
    assert [x["id"] for x in await live(rw, user=gm)] == [e["id"]]
    for user in (rw.cashier_a, keeper):
        r = await rw.client.get("/api/v1/reconciliation/exceptions", headers=auth_headers(user))
        assert r.status_code == 403
