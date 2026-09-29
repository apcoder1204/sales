from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.repositories.branch_repo import branch_repo
from app.schemas.branch import BranchCreate, BranchUpdate
from app.core.exceptions import NotFoundException, DuplicateException, ValidationException
from app.services.audit_service import audit_service


class BranchService:
    async def list_branches(self, db: AsyncSession):
        return await branch_repo.list_all(db)

    async def get_branch(self, db: AsyncSession, branch_id: UUID):
        branch = await branch_repo.get_by_id(db, branch_id)
        if not branch:
            raise NotFoundException("Tawi", "branch")
        return branch

    async def create_branch(self, db: AsyncSession, data: BranchCreate, actor):
        existing = await branch_repo.get_by_name_or_code(db, data.name, data.code)
        if existing:
            field = "jina" if existing.name == data.name else "msimbo"
            raise DuplicateException(f"Tawi lenye {field} hili", "BRANCH_ALREADY_EXISTS")

        try:
            async with db.begin_nested():
                branch = await branch_repo.create(db, data.model_dump())
        except IntegrityError as exc:
            # Narrow race (two concurrent creates for the same name/code), or
            # — for branch_type="main_store" — the partial unique index that
            # allows at most one *active* main store, added when that
            # invariant was hardened. Either way, this is a clean 409, not a
            # raw 500.
            raise DuplicateException("Tawi lenye jina au msimbo huu", "BRANCH_ALREADY_EXISTS") from exc

        await db.commit()
        await audit_service.log(
            db, action="BRANCH_CREATED", category="system",
            user_id=actor.id, username=actor.username, user_role=actor.role.name,
            branch_id=branch.id, entity_type="branch", entity_id=str(branch.id),
            details={"name": branch.name, "code": branch.code, "branch_type": branch.branch_type},
        )
        return branch

    async def update_branch(self, db: AsyncSession, branch_id: UUID, data: BranchUpdate, actor):
        branch = await branch_repo.get_by_id(db, branch_id)
        if not branch:
            raise NotFoundException("Tawi", "branch")

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return branch

        if "name" in updates or "code" in updates:
            existing = await branch_repo.get_by_name_or_code(
                db, updates.get("name", branch.name), updates.get("code", branch.code), exclude_id=branch_id
            )
            if existing:
                field = "jina" if existing.name == updates.get("name", branch.name) else "msimbo"
                raise DuplicateException(f"Tawi lenye {field} hili", "BRANCH_ALREADY_EXISTS")

        # Would this update leave the system with zero active main stores?
        # A DB constraint stops a *second* one from ever existing, but
        # nothing stops removing the only one — store_keeper's entire scope
        # (and every "ship from the main store" flow) depends on exactly one
        # always existing.
        becomes_inactive = updates.get("is_active") is False
        becomes_non_main = updates.get("branch_type") == "pos_point"
        if branch.branch_type == "main_store" and branch.is_active and (becomes_inactive or becomes_non_main):
            other_active = await branch_repo.count_other_active_main_stores(db, branch_id)
            if other_active == 0:
                raise ValidationException(
                    "Haiwezekani kuzima au kubadilisha aina ya Ghala Kuu pekee linalofanya kazi. "
                    "Anzisha Ghala Kuu jingine kwanza.",
                    "LAST_ACTIVE_MAIN_STORE",
                )

        try:
            async with db.begin_nested():
                branch = await branch_repo.update(db, branch_id, updates)
        except IntegrityError as exc:
            raise DuplicateException("Tawi lenye jina au msimbo huu", "BRANCH_ALREADY_EXISTS") from exc

        await db.commit()
        await audit_service.log(
            db, action="BRANCH_UPDATED", category="system",
            user_id=actor.id, username=actor.username, user_role=actor.role.name,
            branch_id=branch.id, entity_type="branch", entity_id=str(branch.id),
            details={"updated_fields": list(updates.keys())},
        )
        return branch

    async def delete_branch(self, db: AsyncSession, branch_id: UUID, actor) -> dict:
        """Hard-deletes only a branch with zero history anywhere in the
        schema (mirrors user_service.permanently_delete_user's precedent for
        the same class of decision). Anything with real activity is
        deactivated instead — the branch stays visible (as inactive) so
        every historical sale/closing/transfer that references it keeps a
        meaningful branch name rather than a dangling ID."""
        branch = await branch_repo.get_by_id(db, branch_id)
        if not branch:
            raise NotFoundException("Tawi", "branch")

        if branch.branch_type == "main_store" and branch.is_active:
            other_active = await branch_repo.count_other_active_main_stores(db, branch_id)
            if other_active == 0:
                raise ValidationException(
                    "Haiwezekani kufuta au kuzima Ghala Kuu pekee linalofanya kazi. "
                    "Anzisha Ghala Kuu jingine kwanza.",
                    "LAST_ACTIVE_MAIN_STORE",
                )

        history = await branch_repo.get_history_counts(db, branch_id)
        blocking = {k: v for k, v in history.items() if v > 0}

        if blocking:
            await branch_repo.update(db, branch_id, {"is_active": False})
            await db.commit()
            await audit_service.log(
                db, action="BRANCH_DEACTIVATED", category="system",
                user_id=actor.id, username=actor.username, user_role=actor.role.name,
                branch_id=branch.id, entity_type="branch", entity_id=str(branch.id),
                details={"name": branch.name, "reason": "has_history", "history": blocking},
            )
            return {"deleted": False, "deactivated": True, "message": "Tawi lina historia ya shughuli — limezimwa badala ya kufutwa."}

        await branch_repo.hard_delete(db, branch_id)
        await db.commit()
        # Deliberately no branch_id= here (unlike every other audit_service.log
        # call in this file) — audit_logs.branch_id is a real FK with no
        # ON DELETE SET NULL, and the branch row is already gone by this
        # point. entity_id (a plain string column, not an FK) carries the
        # deleted branch's ID instead.
        await audit_service.log(
            db, action="BRANCH_DELETED", category="system",
            user_id=actor.id, username=actor.username, user_role=actor.role.name,
            entity_type="branch", entity_id=str(branch_id),
            details={"name": branch.name, "code": branch.code},
        )
        return {"deleted": True, "deactivated": False, "message": "Tawi limefutwa."}


branch_service = BranchService()
