from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.authorization import get_main_store_id, get_active_branch_or_error, is_global_scope
from app.schemas.audit_log import AuditLogResponse, AuditLogFilter
from app.repositories.audit_repo import audit_repo
import math

router = APIRouter(prefix="/audit-logs", tags=["Kumbukumbu"])


@router.get("")
async def list_audit_logs(
    category: str | None = None,
    user_id: UUID | None = None,
    action: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    page: int = 1, per_page: int = 50,
    current_user=Depends(require_role("super_admin", "admin", "store_keeper", "general_manager")),
    db: AsyncSession = Depends(get_db),
):
    role = current_user.role.name
    if role == "store_keeper":
        category = "inventory"
        branch_id = await get_main_store_id(db)
    elif role == "general_manager":
        # Client-supplied category must never override this — general_manager
        # is restricted to transfers-category audit events.
        category = "transfers"
        if branch_id is not None:
            await get_active_branch_or_error(db, branch_id, "Tawi")
    elif is_global_scope(current_user):
        # super_admin/admin: an explicit branch-context selection is
        # honored (validated against real branches) so their audit view can
        # follow the global branch switcher; omitted/None still means the
        # unrestricted ALL-branches view, including genuinely global/
        # system-level events that were never tied to one branch.
        if branch_id is not None:
            await get_active_branch_or_error(db, branch_id, "Tawi")

    skip = (page - 1) * per_page
    rows, total = await audit_repo.list_logs(
        db, category, user_id, action, from_date, to_date, skip, per_page, branch_id
    )
    items = [
        AuditLogResponse(
            id=r.id, username=r.username, user_role=r.user_role,
            branch=None, action=r.action, category=r.category,
            entity_type=r.entity_type, entity_id=r.entity_id,
            details=r.details, ip_address=r.ip_address, created_at=r.created_at,
        ) for r in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": math.ceil(total / per_page) if total else 1}
