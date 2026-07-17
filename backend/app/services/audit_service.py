from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.audit_repo import audit_repo
import logging

logger = logging.getLogger("dukani.audit")


class AuditService:
    async def log(
        self, db: AsyncSession, *,
        action: str, category: str,
        username: str, user_role: str,
        user_id: UUID | None = None,
        branch_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        try:
            await audit_repo.create(db, {
                "user_id": user_id,
                "username": username,
                "user_role": user_role,
                "branch_id": branch_id,
                "action": action,
                "category": category,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
                "ip_address": ip_address,
            })
            await db.commit()
        except Exception as e:
            logger.error(f"Audit log failed: {e}")


audit_service = AuditService()
