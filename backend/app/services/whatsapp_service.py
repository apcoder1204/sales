"""WhatsApp report sharing: receiver-number setting and (later) sending.

The receiver number is read server-side only — either pinned by the
WHATSAPP_RECEIVER_OVERRIDE env var (demo site, shared logins) or stored in
app_settings by an admin. Clients never choose where a report goes.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ValidationException, WhatsAppReceiverLockedException
from app.models.app_setting import AppSetting
from app.services.audit_service import audit_service

RECEIVER_KEY = "whatsapp_report_number"

_SEPARATORS = re.compile(r"[\s\-()]")


def normalize_phone(raw: str) -> str:
    """Normalise a phone number to international digits without '+'
    (e.g. '0712 345 678' -> '255712345678'). Local Tanzanian numbers
    (leading single 0, 10 digits) get the 255 country code."""
    s = _SEPARATORS.sub("", raw or "")
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("00"):
        s = s[2:]
    elif s.startswith("0") and len(s) == 10:
        s = "255" + s[1:]
    if not s.isdigit() or not (10 <= len(s) <= 15):
        raise ValidationException("Namba ya simu si sahihi", code="INVALID_PHONE")
    return s


async def get_receiver(db: AsyncSession) -> tuple[str | None, bool]:
    """(number, locked). locked=True when the number is pinned by env."""
    if settings.WHATSAPP_RECEIVER_OVERRIDE:
        return normalize_phone(settings.WHATSAPP_RECEIVER_OVERRIDE), True
    row = await db.get(AppSetting, RECEIVER_KEY)
    return (row.value if row else None), False


async def set_receiver(db: AsyncSession, raw: str, user) -> str:
    if settings.WHATSAPP_RECEIVER_OVERRIDE:
        raise WhatsAppReceiverLockedException()
    number = normalize_phone(raw)
    row = await db.get(AppSetting, RECEIVER_KEY)
    old = row.value if row else None
    if row:
        row.value = number
        row.updated_by = user.id
    else:
        db.add(AppSetting(key=RECEIVER_KEY, value=number, updated_by=user.id))
    await db.flush()
    await audit_service.log(
        db, action="WHATSAPP_RECEIVER_SET", category="system",
        user_id=user.id, username=user.username, user_role=user.role.name,
        entity_type="app_setting", entity_id=RECEIVER_KEY,
        details={"old": old, "new": number},
    )
    return number
