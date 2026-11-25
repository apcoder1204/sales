"""Genuine cross-connection concurrency for WhatsApp sends — see
test_transfer_true_concurrency.py for why this can't use the rolled-back
savepoint fixtures. Two independent sessions send the same report at the
same moment (a double-click, or two staff on the same closing): the
advisory lock must let exactly one reach WhatsApp; the other is refused as
a duplicate. Commits a real user, then deletes everything it created."""
import asyncio
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.core.exceptions import WhatsAppException
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.services import whatsapp_service
from tests.conftest import UTC_CONNECT_ARGS


class SlowGateway:
    """Holds the 'send' open long enough for the second request to arrive
    while the first still holds the lock."""
    def __init__(self):
        self.calls = 0

    async def send_document(self, phone, pdf, filename, caption):
        self.calls += 1
        await asyncio.sleep(0.5)


async def test_concurrent_same_report_sends_once(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_RECEIVER_OVERRIDE", "0712345678")
    monkeypatch.setattr(settings, "WHATSAPP_DAILY_CAP", 10_000)
    engine = create_async_engine(settings.DATABASE_URL, connect_args=UTC_CONNECT_ARGS)
    setup = AsyncSession(bind=engine, expire_on_commit=False)
    user_id = None
    try:
        suffix = uuid.uuid4().hex[:8]
        role = (await setup.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        user = User(
            username=f"conc_wa_{suffix}", full_name="Concurrency Sender",
            email=f"conc_wa_{suffix}@test.local", password_hash=hash_password("Test1234"),
            role_id=role.id, is_active=True,
        )
        setup.add(user)
        await setup.commit()
        user_id = user.id

        gateway = SlowGateway()
        session_a = AsyncSession(bind=engine, expire_on_commit=False)
        session_b = AsyncSession(bind=engine, expire_on_commit=False)
        user_a = await session_a.get(User, user_id)
        user_b = await session_b.get(User, user_id)
        title = f"Concurrency {suffix}"

        async def attempt(session, u, n):
            try:
                await whatsapp_service.send_report(
                    session, u, gateway, pdf=b"%PDF-1.4 " + str(n).encode(),
                    filename="r.pdf", report_type="sales", title=title,
                    period_label="Leo", branch_id=None, ip=None,
                )
                return "sent"
            except WhatsAppException as e:
                return e.detail["code"]
            finally:
                await session.close()

        results = await asyncio.gather(attempt(session_a, user_a, 1), attempt(session_b, user_b, 2))

        assert sorted(results) == ["WHATSAPP_DUPLICATE", "sent"]
        assert gateway.calls == 1
    finally:
        if user_id:
            await setup.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
            await setup.execute(delete(User).where(User.id == user_id))
            await setup.commit()
        await setup.close()
        await engine.dispose()
