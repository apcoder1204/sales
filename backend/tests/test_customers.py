"""Customer master records (spec §6.2 customers, §6.5 permissions)."""
import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import auth_headers, make_branch, make_customer, make_user


async def _audit(db, action, entity_id):
    rows = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == str(entity_id))
        )
    ).scalars().all()
    return rows


async def _cashier(db):
    branch = await make_branch(db)
    return await make_user(db, "cashier", branch=branch)


@pytest.mark.asyncio
async def test_cashier_creates_customer(client, db_session):
    cashier = await _cashier(db_session)
    r = await client.post(
        "/api/v1/customers",
        json={"name": "Juma Ali", "phone": "0712345678"},
        headers=auth_headers(cashier),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["phone"] == "255712345678"
    assert re.match(r"^CUS-\d{4,}$", body["customer_no"])
    assert body["credit_limit"] == "0.00"
    assert body["status"] == "active"
    assert await _audit(db_session, "CUSTOMER_CREATED", body["id"])


@pytest.mark.asyncio
async def test_duplicate_phone_rejected(client, db_session):
    cashier = await _cashier(db_session)
    h = auth_headers(cashier)
    r1 = await client.post("/api/v1/customers", json={"name": "A One", "phone": "0712345679"}, headers=h)
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/api/v1/customers", json={"name": "B Two", "phone": "+255 712 345 679"}, headers=h
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "CUSTOMER_PHONE_DUPLICATE"


@pytest.mark.asyncio
async def test_invalid_phone_rejected(client, db_session):
    cashier = await _cashier(db_session)
    r = await client.post(
        "/api/v1/customers", json={"name": "Bad Phone", "phone": "12ab"},
        headers=auth_headers(cashier),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_by_name_phone_number(client, db_session):
    cashier = await _cashier(db_session)
    h = auth_headers(cashier)
    r = await client.post(
        "/api/v1/customers",
        json={"name": "Zawadi Mfinanga Searchable", "phone": "0712999111"},
        headers=h,
    )
    created = r.json()
    for q in ("Mfinanga Search", "0712999", created["customer_no"]):
        res = await client.get("/api/v1/customers", params={"q": q}, headers=h)
        assert res.status_code == 200, res.text
        ids = [c["id"] for c in res.json()["items"]]
        assert created["id"] in ids, q


@pytest.mark.asyncio
async def test_cashier_cannot_change_credit(client, db_session):
    cashier = await _cashier(db_session)
    customer = await make_customer(db_session)
    r = await client.put(
        f"/api/v1/customers/{customer.id}/credit",
        json={"credit_limit": "100000", "credit_days": 30, "status": "active", "reason": "trusted"},
        headers=auth_headers(cashier),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_changes_credit_audited(client, db_session):
    admin = await make_user(db_session, "admin")
    customer = await make_customer(db_session)
    r = await client.put(
        f"/api/v1/customers/{customer.id}/credit",
        json={"credit_limit": "2000000", "credit_days": 45, "status": "active",
              "reason": "Mteja mwaminifu"},
        headers=auth_headers(admin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["credit_limit"] == "2000000.00"
    rows = await _audit(db_session, "CUSTOMER_CREDIT_CHANGED", customer.id)
    assert len(rows) == 1
    d = rows[0].details
    assert d["old_limit"] == "0.00"
    assert d["new_limit"] == "2000000.00"
    assert d["reason"] == "Mteja mwaminifu"
    assert d["old_days"] == 30 and d["new_days"] == 45
    assert "current_exposure" in d


@pytest.mark.asyncio
async def test_cashier_update_cannot_touch_credit_fields(client, db_session):
    cashier = await _cashier(db_session)
    customer = await make_customer(db_session)
    r = await client.put(
        f"/api/v1/customers/{customer.id}",
        json={"name": "New Name", "credit_limit": "9999999"},
        headers=auth_headers(cashier),
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "New Name"
    assert r.json()["credit_limit"] == "0.00"
    assert await _audit(db_session, "CUSTOMER_UPDATED", customer.id)


@pytest.mark.asyncio
async def test_store_keeper_cannot_list_customers(client, db_session):
    sk = await make_user(db_session, "store_keeper")
    r = await client.get("/api/v1/customers", headers=auth_headers(sk))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_general_manager_cannot_create_customer(client, db_session):
    gm = await make_user(db_session, "general_manager")
    r = await client.post(
        "/api/v1/customers", json={"name": "GM Made", "phone": "0712000999"},
        headers=auth_headers(gm),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_no_delete_route(client, db_session):
    admin = await make_user(db_session, "admin")
    customer = await make_customer(db_session)
    r = await client.delete(f"/api/v1/customers/{customer.id}", headers=auth_headers(admin))
    assert r.status_code == 405


@pytest.mark.asyncio
async def test_deactivate_customer(client, db_session):
    admin = await make_user(db_session, "admin")
    customer = await make_customer(db_session, credit_limit=Decimal("100000"))
    h = auth_headers(admin)
    r = await client.put(
        f"/api/v1/customers/{customer.id}/credit",
        json={"credit_limit": "100000", "credit_days": 30, "status": "inactive",
              "reason": "Amehama mji"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    got = await client.get(f"/api/v1/customers/{customer.id}", headers=h)
    assert got.status_code == 200
    assert got.json()["customer"]["status"] == "inactive"


@pytest.mark.asyncio
async def test_customer_list_includes_scoped_balance(client, db_session):
    import uuid as _uuid
    from app.core.business_time import business_date_today
    from app.services import ledger_service

    a = await make_branch(db_session)
    b = await make_branch(db_session)
    admin = await make_user(db_session, "admin")
    cashier_b = await make_user(db_session, "cashier", branch=b)
    customer = await make_customer(db_session, credit_limit=Decimal("1000000"), name="Zuberi Listbalance")
    for branch, amount in ((a, "300000"), (b, "200000")):
        await ledger_service.post(
            db_session, customer_id=customer.id, branch_id=branch.id, entry_type="opening_balance",
            source_type="opening_balance", source_id=_uuid.uuid4(), business_date=business_date_today(),
            description="t", created_by=admin.id, debit=Decimal(amount),
        )

    async def item(user):
        r = await client.get("/api/v1/customers", params={"q": "Zuberi Listbalance"}, headers=auth_headers(user))
        assert r.status_code == 200, r.text
        return next(c for c in r.json()["items"] if c["id"] == str(customer.id))

    mine = await item(cashier_b)
    assert mine["balance"] == "200000.00"
    assert mine["available_credit"] == "500000.00"
    assert "overdue" in mine and "last_payment_at" in mine
    assert (await item(admin))["balance"] == "500000.00"
