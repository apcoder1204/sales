"""WhatsApp report sharing: receiver-number setting and (later) sending.

The receiver number is read server-side only — either pinned by the
WHATSAPP_RECEIVER_OVERRIDE env var (demo site, shared logins) or stored in
app_settings by an admin. Clients never choose where a report goes.
"""
import hashlib
import re
import unicodedata
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.phone import normalize_phone  # noqa: F401 — re-exported
from app.core.authorization import resolve_read_branch_id
from app.core.business_time import business_date_today, utc_range_for_business_date, utcnow
from app.core.exceptions import (
    InsufficientPermissionException,
    ValidationException,
    WhatsAppReceiverLockedException,
    whatsapp_error,
)
from app.models.app_setting import AppSetting
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.services.audit_service import audit_service
from app.services.whatsapp_gateway import (
    GatewayError,
    GatewaySessionNotReady,
    GatewayTimeout,
    GatewayUnreachable,
    WhatsAppGateway,
)

RECEIVER_KEY = "whatsapp_report_number"


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


# ── Sending ──────────────────────────────────────────────────────────────────

SEND_ACTION = "WHATSAPP_REPORT_SEND"
MAX_PDF_BYTES = 10 * 1024 * 1024
DUPLICATE_WINDOW = timedelta(minutes=10)
# Arbitrary constant key for pg_advisory_xact_lock: serialises sends so the
# daily-cap and duplicate checks are exact across gunicorn workers.
_SEND_LOCK_KEY = 715001

_FINANCIAL = ("super_admin", "admin", "general_manager")
_STOCK = ("super_admin", "admin", "general_manager", "store_keeper")

# Copied from the read gates of the matching report endpoints
# (app/api/v1/reports.py, app/api/v1/inventory.py, app/api/v1/debt_reports.py) — a role may only send a
# report type it is allowed to view.
REPORT_TYPE_ROLES: dict[str, tuple[str, ...]] = {
    "sales": _FINANCIAL,
    "branch_performance": _FINANCIAL,
    "cashier_performance": _FINANCIAL,
    "profit_loss": _FINANCIAL,
    "inventory": _STOCK,
    "low_stock": _STOCK,
    "inventory_valuation": _STOCK,
    "stock_movements": _STOCK + ("cashier",),
    "closing": _FINANCIAL + ("cashier",),
    # Debt reports (app/api/v1/debt_reports.py) and the customer statement.
    "debt_outstanding": _FINANCIAL + ("cashier",),
    "debt_overdue": _FINANCIAL + ("cashier",),
    "debt_ageing": _FINANCIAL + ("cashier",),
    "debt_collections": _FINANCIAL + ("cashier",),
    "debt_branches": _FINANCIAL + ("cashier",),
    "customer_statement": _FINANCIAL + ("cashier",),
    "debt_credit_utilization": _FINANCIAL,
    "debt_opening_balances": ("super_admin", "admin", "cashier"),
    "debt_reconciliation": _FINANCIAL,
}


def _clean(value: str, limit: int) -> str:
    """Drop control characters (newlines/tabs become spaces) and collapse
    whitespace, so client text can't break the caption's layout."""
    chars = []
    for ch in value or "":
        if ch in "\n\r\t":
            chars.append(" ")
        elif unicodedata.category(ch) != "Cc":
            chars.append(ch)
    return " ".join("".join(chars).split())[:limit]


_FILENAME_OK = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str | None) -> str:
    base = _FILENAME_OK.sub("_", (name or "").rsplit("/", 1)[-1]).strip("._")[:100]
    if not base:
        return "ripoti.pdf"
    return base if base.lower().endswith(".pdf") else f"{base}.pdf"


async def _sent_today_count(db: AsyncSession) -> int:
    start, end = utc_range_for_business_date(business_date_today())
    return await db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == SEND_ACTION,
            AuditLog.details["status"].astext == "sent",
            AuditLog.created_at >= start,
            AuditLog.created_at <= end,
        )
    ) or 0


def _report_key(report_type: str, title: str, period_label: str, branch_id: UUID | None) -> str:
    """Identifies *which report* is being sent, independent of the PDF bytes:
    browser-built PDFs embed a generation timestamp, so re-sending the same
    report produces a different file every time."""
    raw = f"{report_type}|{title}|{period_label}|{branch_id or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _recently_sent(db: AsyncSession, report_key: str) -> bool:
    since = utcnow() - DUPLICATE_WINDOW
    found = await db.scalar(
        select(AuditLog.id).where(
            AuditLog.action == SEND_ACTION,
            AuditLog.details["status"].astext == "sent",
            AuditLog.details["report_key"].astext == report_key,
            AuditLog.created_at >= since,
        ).limit(1)
    )
    return found is not None


async def send_report(
    db: AsyncSession, user, gateway: WhatsAppGateway, *,
    pdf: bytes, filename: str | None, report_type: str, title: str,
    period_label: str, branch_id: UUID | None, ip: str | None,
) -> None:
    if not settings.WHATSAPP_ENABLED:
        raise whatsapp_error("WHATSAPP_DISABLED")
    if user.role.name not in REPORT_TYPE_ROLES.get(report_type, ()):
        raise InsufficientPermissionException()
    if len(pdf) > MAX_PDF_BYTES:
        raise whatsapp_error("WHATSAPP_PDF_TOO_LARGE")
    if not pdf.startswith(b"%PDF"):
        raise whatsapp_error("WHATSAPP_INVALID_PDF")
    receiver, _ = await get_receiver(db)
    if not receiver:
        raise whatsapp_error("WHATSAPP_NO_RECEIVER")

    resolved_branch_id = await resolve_read_branch_id(db, user, branch_id)
    branch = await db.get(Branch, resolved_branch_id) if resolved_branch_id else None
    title = _clean(title, 120)
    period_label = _clean(period_label, 60)
    sha256 = hashlib.sha256(pdf).hexdigest()
    report_key = _report_key(report_type, title, period_label, resolved_branch_id)

    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SEND_LOCK_KEY})
    if await _sent_today_count(db) >= settings.WHATSAPP_DAILY_CAP:
        await db.rollback()
        raise whatsapp_error("WHATSAPP_DAILY_CAP", {"cap": settings.WHATSAPP_DAILY_CAP})
    if await _recently_sent(db, report_key):
        await db.rollback()
        raise whatsapp_error("WHATSAPP_DUPLICATE")

    lines = [f"{settings.WHATSAPP_CAPTION_PREFIX}*{title}*"]
    if branch:
        lines.append(branch.name)
    if period_label:
        lines.append(period_label)
    lines.append(f"Imetumwa na: {user.full_name}")
    caption = "\n".join(lines)

    status, error_code = "sent", None
    try:
        await gateway.send_document(receiver, pdf, _safe_filename(filename), caption)
    except GatewayTimeout:
        status, error_code = "unknown", "WHATSAPP_TIMEOUT"
    except (GatewaySessionNotReady, GatewayUnreachable):
        status, error_code = "failed", "WHATSAPP_NOT_CONNECTED"
    except GatewayError:
        status, error_code = "failed", "WHATSAPP_SEND_FAILED"

    details = {
        "report_type": report_type, "title": title, "period_label": period_label,
        "sha256": sha256, "report_key": report_key, "status": status,
    }
    if error_code:
        details["error_code"] = error_code
    # audit_service.log commits, which also releases the advisory lock.
    await audit_service.log(
        db, action=SEND_ACTION, category="system",
        user_id=user.id, username=user.username, user_role=user.role.name,
        branch_id=resolved_branch_id, entity_type="report", entity_id=report_type,
        details=details, ip_address=ip,
    )
    if error_code:
        raise whatsapp_error(error_code)
