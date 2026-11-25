import base64
import json

import httpx
import pytest

from app.config import settings
from app.main import app as fastapi_app
from app.services.whatsapp_gateway import (
    GatewayRejected,
    GatewaySessionNotReady,
    GatewayTimeout,
    GatewayUnreachable,
    WhatsAppGateway,
    get_whatsapp_gateway,
)
from tests.conftest import auth_headers, make_user

PDF = b"%PDF-1.4 test document"


def _gateway(handler) -> WhatsAppGateway:
    return WhatsAppGateway(
        base_url="http://openwa.test/api", api_key="k", session_id="S1",
        timeout=5, transport=httpx.MockTransport(handler),
    )


async def test_send_document_payload():
    seen = {}

    def handler(request: httpx.Request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("X-API-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "msg1"})

    await _gateway(handler).send_document("255712345678", PDF, "ripoti.pdf", "caption here")

    assert seen["method"] == "POST"
    assert seen["path"] == "/api/sessions/S1/messages/send-document"
    assert seen["key"] == "k"
    body = seen["body"]
    assert body["chatId"] == "255712345678@c.us"
    assert body["mimetype"] == "application/pdf"
    assert base64.b64decode(body["base64"]) == PDF
    assert body["filename"] == "ripoti.pdf"
    assert body["caption"] == "caption here"


@pytest.mark.parametrize(
    "response_or_exc, expected",
    [
        (httpx.Response(500, json={"message": "boom"}), GatewayRejected),
        (httpx.Response(401, json={"message": "bad key"}), GatewayRejected),
        (httpx.Response(409, json={"message": "not ready"}), GatewaySessionNotReady),
        (httpx.Response(404, json={"message": "no session"}), GatewaySessionNotReady),
        # Real OpenWA 0.32.1 answer for a session that was never started.
        (httpx.Response(400, json={"message": "Session 'S1' is not active. Start the session first."}),
         GatewaySessionNotReady),
        (httpx.Response(400, json={"message": "chatId must be a string"}), GatewayRejected),
        (httpx.ConnectError("refused"), GatewayUnreachable),
        (httpx.ReadTimeout("slow"), GatewayTimeout),
    ],
)
async def test_send_document_errors(response_or_exc, expected):
    def handler(request):
        if isinstance(response_or_exc, Exception):
            raise response_or_exc
        return response_or_exc

    with pytest.raises(expected):
        await _gateway(handler).send_document("255712345678", PDF, "r.pdf", "c")


async def test_session_status_ready():
    def handler(request):
        assert request.url.path == "/api/sessions/S1"
        return httpx.Response(200, json={"id": "S1", "status": "ready"})

    assert await _gateway(handler).session_status() == "ready"


async def test_session_status_unreachable_never_raises():
    def handler(request):
        raise httpx.ConnectError("refused")

    assert await _gateway(handler).session_status() == "unreachable"


async def test_status_when_gateway_unreachable(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "")

    def handler(request):
        raise httpx.ConnectError("refused")

    fastapi_app.dependency_overrides[get_whatsapp_gateway] = lambda: _gateway(handler)
    # Independent of any receiver saved in the shared dev DB (the test's
    # transaction is rolled back, so deleting here is safe).
    from app.models.app_setting import AppSetting
    from app.services.whatsapp_service import RECEIVER_KEY
    row = await db_session.get(AppSetting, RECEIVER_KEY)
    if row:
        await db_session.delete(row)
        await db_session.flush()
    cashier = await make_user(db_session, "cashier")
    resp = await client.get("/api/v1/whatsapp/status", headers=auth_headers(cashier))
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True, "configured": False, "connected": False}


async def test_status_connected_and_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "0712345678")
    fastapi_app.dependency_overrides[get_whatsapp_gateway] = lambda: _gateway(
        lambda r: httpx.Response(200, json={"id": "S1", "status": "ready"})
    )
    admin = await make_user(db_session, "admin")
    resp = await client.get("/api/v1/whatsapp/status", headers=auth_headers(admin))
    assert resp.json() == {"enabled": True, "configured": True, "connected": True}
    resp = await client.get("/api/v1/whatsapp/settings", headers=auth_headers(admin))
    assert resp.json()["connected"] is True


async def test_status_disabled_skips_gateway(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", False)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"status": "ready"})

    fastapi_app.dependency_overrides[get_whatsapp_gateway] = lambda: _gateway(handler)
    admin = await make_user(db_session, "admin")
    resp = await client.get("/api/v1/whatsapp/status", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["connected"] is False
    assert calls == []
