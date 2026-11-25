import pytest
from sqlalchemy import select

from app.config import settings
from app.core.exceptions import ValidationException
from app.models.audit_log import AuditLog
from app.services.whatsapp_service import normalize_phone
from tests.conftest import auth_headers, make_user


def test_normalize_phone_local_formats():
    assert normalize_phone("0712 345 678") == "255712345678"
    assert normalize_phone("+255 712-345-678") == "255712345678"
    assert normalize_phone("255712345678") == "255712345678"
    assert normalize_phone("00255712345678") == "255712345678"
    assert normalize_phone("(0712) 345 678") == "255712345678"


@pytest.mark.parametrize("raw", ["abc", "0712", "", "+1234", "1234567890123456", "07123456789x"])
def test_normalize_phone_rejects_junk(raw):
    with pytest.raises(ValidationException):
        normalize_phone(raw)


async def test_admin_sets_and_reads_receiver(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "")
    admin = await make_user(db_session, "admin")

    resp = await client.put(
        "/api/v1/whatsapp/settings", json={"number": "0712345678"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["number"] == "255712345678"

    resp = await client.get("/api/v1/whatsapp/settings", headers=auth_headers(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["number"] == "255712345678"
    assert body["locked"] is False


async def test_invalid_number_rejected(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "")
    admin = await make_user(db_session, "admin")
    resp = await client.put(
        "/api/v1/whatsapp/settings", json={"number": "hello"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_PHONE"


async def test_cashier_cannot_read_or_set_settings(client, db_session):
    cashier = await make_user(db_session, "cashier")
    resp = await client.get("/api/v1/whatsapp/settings", headers=auth_headers(cashier))
    assert resp.status_code == 403
    resp = await client.put(
        "/api/v1/whatsapp/settings", json={"number": "0712345678"}, headers=auth_headers(cashier)
    )
    assert resp.status_code == 403


async def test_override_locks_receiver(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "+255700000001")
    admin = await make_user(db_session, "admin")

    resp = await client.get("/api/v1/whatsapp/settings", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["number"] == "255700000001"
    assert resp.json()["locked"] is True

    resp = await client.put(
        "/api/v1/whatsapp/settings", json={"number": "0712345678"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "WHATSAPP_RECEIVER_LOCKED"


async def test_set_receiver_is_audited(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "")
    admin = await make_user(db_session, "admin")
    resp = await client.put(
        "/api/v1/whatsapp/settings", json={"number": "0712345678"}, headers=auth_headers(admin)
    )
    assert resp.status_code == 200
    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "WHATSAPP_RECEIVER_SET", AuditLog.user_id == admin.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
