import re

import pytest
from sqlalchemy import select

from app.config import settings
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.services.whatsapp_gateway import (
    GatewaySessionNotReady,
    GatewayTimeout,
    get_whatsapp_gateway,
)
from app.services.whatsapp_service import set_receiver
from tests.conftest import auth_headers, make_branch, make_user

URL = "/api/v1/whatsapp/send-report"


def pdf(n: int = 0) -> bytes:
    return b"%PDF-1.4 report body " + str(n).encode()


class FakeGateway:
    def __init__(self):
        self.calls: list[dict] = []
        self.raise_exc: Exception | None = None

    async def session_status(self) -> str:
        return "ready"

    async def send_document(self, phone, pdf_bytes, filename, caption):
        self.calls.append({"phone": phone, "pdf": pdf_bytes, "filename": filename, "caption": caption})
        if self.raise_exc:
            raise self.raise_exc


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "")
    monkeypatch.setattr(settings, "WHATSAPP_CAPTION_PREFIX", "")
    monkeypatch.setattr(settings, "WHATSAPP_DAILY_CAP", 50)
    fake = FakeGateway()
    fastapi_app.dependency_overrides[get_whatsapp_gateway] = lambda: fake
    return fake


async def _with_receiver(db_session):
    admin = await make_user(db_session, "admin")
    await set_receiver(db_session, "0712345678", admin)
    return admin


async def _send(client, user, *, body: bytes | None = None, report_type="sales",
                title="Ripoti ya Mauzo", period_label="Leo", branch_id=None):
    data = {"report_type": report_type, "title": title, "period_label": period_label}
    if branch_id:
        data["branch_id"] = str(branch_id)
    return await client.post(
        URL, headers=auth_headers(user), data=data,
        files={"file": ("ripoti_mauzo.pdf", body if body is not None else pdf(), "application/pdf")},
    )


async def _audits(db_session, user):
    return (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "WHATSAPP_REPORT_SEND", AuditLog.user_id == user.id
            )
        )
    ).scalars().all()


async def test_admin_sends_report(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    resp = await _send(client, admin)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "sent"}
    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["phone"] == "255712345678"
    assert call["pdf"] == pdf()
    assert call["filename"] == "ripoti_mauzo.pdf"
    assert "*Ripoti ya Mauzo*" in call["caption"]
    assert f"Imetumwa na: {admin.full_name}" in call["caption"]
    audits = await _audits(db_session, admin)
    assert len(audits) == 1
    assert audits[0].details["status"] == "sent"
    assert re.fullmatch(r"[0-9a-f]{64}", audits[0].details["sha256"])


async def test_cashier_cannot_send_sales_report(client, db_session, gateway):
    await _with_receiver(db_session)
    branch = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch)
    resp = await _send(client, cashier, report_type="sales")
    assert resp.status_code == 403
    assert gateway.calls == []


async def test_unknown_report_type_refused(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    resp = await _send(client, admin, report_type="anything")
    assert resp.status_code == 403
    assert gateway.calls == []


async def test_cashier_caption_uses_own_branch(client, db_session, gateway):
    await _with_receiver(db_session)
    branch_a = await make_branch(db_session)
    branch_b = await make_branch(db_session)
    cashier = await make_user(db_session, "cashier", branch=branch_a)
    resp = await _send(client, cashier, report_type="closing", title="Ufungaji", branch_id=branch_b.id)
    assert resp.status_code == 200, resp.text
    caption = gateway.calls[0]["caption"]
    assert branch_a.name in caption
    assert branch_b.name not in caption


async def test_rejects_non_pdf(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    resp = await _send(client, admin, body=b"hello")
    assert resp.status_code == 400
    assert resp.json()["code"] == "WHATSAPP_INVALID_PDF"
    assert gateway.calls == []


async def test_rejects_oversize(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    big = b"%PDF" + b"0" * (10 * 1024 * 1024 - 3)
    resp = await _send(client, admin, body=big)
    assert resp.status_code == 413
    assert resp.json()["code"] == "WHATSAPP_PDF_TOO_LARGE"
    assert gateway.calls == []


async def test_no_receiver(client, db_session, gateway):
    admin = await make_user(db_session, "admin")
    # The dev DB may hold a receiver set via the UI; this test runs inside a
    # rolled-back transaction, so clearing it here is safe.
    from app.models.app_setting import AppSetting
    from app.services.whatsapp_service import RECEIVER_KEY
    row = await db_session.get(AppSetting, RECEIVER_KEY)
    if row:
        await db_session.delete(row)
        await db_session.flush()
    resp = await _send(client, admin)
    assert resp.status_code == 400
    assert resp.json()["code"] == "WHATSAPP_NO_RECEIVER"


async def test_disabled(client, db_session, gateway, monkeypatch):
    admin = await _with_receiver(db_session)
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", False)
    resp = await _send(client, admin)
    assert resp.status_code == 503
    assert resp.json()["code"] == "WHATSAPP_DISABLED"
    assert gateway.calls == []


async def test_duplicate_pdf_refused(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    first = await _send(client, admin, body=pdf(7))
    second = await _send(client, admin, body=pdf(7))
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "WHATSAPP_DUPLICATE"
    assert len(gateway.calls) == 1


async def test_daily_cap(client, db_session, gateway, monkeypatch):
    admin = await _with_receiver(db_session)
    # Count already-sent entries today (dev DB may have some) and cap just above.
    from app.services.whatsapp_service import _sent_today_count
    already = await _sent_today_count(db_session)
    monkeypatch.setattr(settings, "WHATSAPP_DAILY_CAP", already + 2)
    r1 = await _send(client, admin, body=pdf(1))
    r2 = await _send(client, admin, body=pdf(2))
    r3 = await _send(client, admin, body=pdf(3))
    assert (r1.status_code, r2.status_code) == (200, 200)
    assert r3.status_code == 429
    assert r3.json()["code"] == "WHATSAPP_DAILY_CAP"
    assert len(gateway.calls) == 2


async def test_timeout_reports_unknown(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    gateway.raise_exc = GatewayTimeout("slow")
    resp = await _send(client, admin)
    assert resp.status_code == 504
    assert resp.json()["code"] == "WHATSAPP_TIMEOUT"
    audits = await _audits(db_session, admin)
    assert [a.details["status"] for a in audits] == ["unknown"]


async def test_not_connected(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    gateway.raise_exc = GatewaySessionNotReady("not active")
    resp = await _send(client, admin)
    assert resp.status_code == 503
    assert resp.json()["code"] == "WHATSAPP_NOT_CONNECTED"
    audits = await _audits(db_session, admin)
    assert [a.details["status"] for a in audits] == ["failed"]


async def test_demo_prefix(client, db_session, gateway, monkeypatch):
    admin = await _with_receiver(db_session)
    monkeypatch.setattr(settings, "WHATSAPP_CAPTION_PREFIX", "[DEMO] ")
    resp = await _send(client, admin)
    assert resp.status_code == 200
    assert gateway.calls[0]["caption"].startswith("[DEMO] *")


async def test_title_control_chars_stripped(client, db_session, gateway):
    admin = await _with_receiver(db_session)
    resp = await _send(client, admin, title="Ripoti\x00\x07 ya\nMauzo")
    assert resp.status_code == 200
    first_line = gateway.calls[0]["caption"].split("\n")[0]
    assert first_line == "*Ripoti ya Mauzo*"
