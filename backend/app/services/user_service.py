from uuid import UUID
import math
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import user_repo
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundException, DuplicateException, InsufficientPermissionException
from app.services.audit_service import audit_service
from app.schemas.common import PaginatedResponse

# Only super_admin may see, create, or manage accounts with these roles —
# admin gets a scoped view/management surface (store_keeper/general_manager/
# cashier only), per the tiered user-management business rule.
HIDDEN_FROM_ADMIN = ("admin", "super_admin")


async def _get_role_name(db: AsyncSession, role_id: int) -> str | None:
    from app.models.role import Role
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    return role.name if role else None


class UserService:
    async def list_users(self, db: AsyncSession, page: int, per_page: int, caller):
        skip = (page - 1) * per_page
        exclude_roles = list(HIDDEN_FROM_ADMIN) if caller.role.name == "admin" else None
        users, total = await user_repo.list_users(db, skip, per_page, exclude_roles=exclude_roles)
        from app.schemas.user import UserResponse
        items = [
            UserResponse(
                id=u.id, username=u.username, full_name=u.full_name,
                email=u.email, role=u.role.name, role_id=u.role_id,
                branch=u.branch.name if u.branch else None,
                branch_id=u.branch_id, is_active=u.is_active,
                last_login=u.last_login, created_at=u.created_at,
            ) for u in users
        ]
        return PaginatedResponse(
            items=items, total=total, page=page,
            per_page=per_page, pages=math.ceil(total / per_page) if total else 1
        )

    async def create_user(self, db: AsyncSession, data: UserCreate, creator):
        if creator.role.name == "admin":
            target_role_name = await _get_role_name(db, data.role_id)
            if target_role_name in HIDDEN_FROM_ADMIN:
                await audit_service.log(
                    db, action="PERMISSION_DENIED", category="system",
                    user_id=creator.id, username=creator.username, user_role=creator.role.name,
                    details={"reason": "admin_cannot_create_role", "role_id": data.role_id},
                )
                raise InsufficientPermissionException("Huna ruhusa ya kuunda mtumiaji wa aina hii")

        existing = await user_repo.get_by_username(db, data.username)
        if existing:
            raise DuplicateException("Jina la mtumiaji")

        user = await user_repo.create(db, {
            "username": data.username,
            "full_name": data.full_name,
            "email": data.email,
            "password_hash": hash_password(data.password),
            "role_id": data.role_id,
            "branch_id": data.branch_id,
        })
        await db.commit()
        await audit_service.log(
            db, action="USER_CREATED", category="users",
            user_id=creator.id, username=creator.username, user_role=creator.role.name,
            entity_type="user", entity_id=str(user.id),
            details={"username": data.username, "role_id": data.role_id}
        )
        return user

    async def update_user(self, db: AsyncSession, user_id: UUID, data: UserUpdate, editor):
        user = await user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("Mtumiaji")

        if editor.role.name == "admin":
            if user.role.name in HIDDEN_FROM_ADMIN or (
                data.role_id is not None
                and await _get_role_name(db, data.role_id) in HIDDEN_FROM_ADMIN
            ):
                await audit_service.log(
                    db, action="PERMISSION_DENIED", category="system",
                    user_id=editor.id, username=editor.username, user_role=editor.role.name,
                    entity_type="user", entity_id=str(user_id),
                    details={"reason": "admin_cannot_edit_hidden_role"},
                )
                raise InsufficientPermissionException("Huna ruhusa ya kuhariri mtumiaji huyu")

        updates = data.model_dump(exclude_none=True, exclude={"confirm_password"})
        if "password" in updates:
            updates["password_hash"] = hash_password(updates.pop("password"))

        user = await user_repo.update(db, user_id, updates)
        await db.commit()
        await audit_service.log(
            db, action="USER_UPDATED", category="users",
            user_id=editor.id, username=editor.username, user_role=editor.role.name,
            entity_type="user", entity_id=str(user_id),
            details={"updated_fields": list(updates.keys())}
        )
        return user

    async def unlock_user(self, db: AsyncSession, user_id: UUID, editor):
        user = await user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("Mtumiaji")
        if editor.role.name == "admin" and user.role.name in HIDDEN_FROM_ADMIN:
            await audit_service.log(
                db, action="PERMISSION_DENIED", category="system",
                user_id=editor.id, username=editor.username, user_role=editor.role.name,
                entity_type="user", entity_id=str(user_id),
                details={"reason": "admin_cannot_unlock_hidden_role"},
            )
            raise InsufficientPermissionException("Huna ruhusa ya kufanya hivi")
        await user_repo.update(db, user_id, {"locked_until": None, "failed_login_attempts": 0})
        await db.commit()

    async def deactivate_user(self, db: AsyncSession, user_id: UUID, editor):
        user = await user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("Mtumiaji")
        if editor.role.name == "admin" and user.role.name in HIDDEN_FROM_ADMIN:
            await audit_service.log(
                db, action="PERMISSION_DENIED", category="system",
                user_id=editor.id, username=editor.username, user_role=editor.role.name,
                entity_type="user", entity_id=str(user_id),
                details={"reason": "admin_cannot_deactivate_hidden_role"},
            )
            raise InsufficientPermissionException("Huna ruhusa ya kufanya hivi")
        await user_repo.update(db, user_id, {"is_active": False})
        await db.commit()
        await audit_service.log(
            db, action="USER_DEACTIVATED", category="users",
            user_id=editor.id, username=editor.username, user_role=editor.role.name,
            entity_type="user", entity_id=str(user_id),
            details={"username": user.username}
        )


user_service = UserService()
