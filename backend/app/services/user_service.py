from uuid import UUID
import math
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import user_repo
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundException, DuplicateException
from app.services.audit_service import audit_service
from app.schemas.common import PaginatedResponse


class UserService:
    async def list_users(self, db: AsyncSession, page: int, per_page: int):
        skip = (page - 1) * per_page
        users, total = await user_repo.list_users(db, skip, per_page)
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

        updates = data.model_dump(exclude_none=True)
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

    async def deactivate_user(self, db: AsyncSession, user_id: UUID, editor):
        user = await user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("Mtumiaji")
        await user_repo.update(db, user_id, {"is_active": False})
        await db.commit()
        await audit_service.log(
            db, action="USER_DEACTIVATED", category="users",
            user_id=editor.id, username=editor.username, user_role=editor.role.name,
            entity_type="user", entity_id=str(user_id),
            details={"username": user.username}
        )


user_service = UserService()
