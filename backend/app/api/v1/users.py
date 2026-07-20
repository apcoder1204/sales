from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.dependencies import require_role, get_current_user
from app.schemas.user import UserCreate, UserUpdate, UserResponse, RoleResponse
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["Watumiaji"])


@router.get("/branches")
async def list_branches(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.branch import Branch
    rows = (await db.execute(select(Branch).where(Branch.is_active == True).order_by(Branch.name))).scalars().all()
    return [{"id": str(b.id), "name": b.name, "code": b.code, "branch_type": b.branch_type} for b in rows]

_super = Depends(require_role("super_admin"))


@router.get("/roles", response_model=list[RoleResponse], dependencies=[_super])
async def list_roles(db: AsyncSession = Depends(get_db)):
    from app.models.role import Role
    rows = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
    return rows


@router.get("", response_model=PaginatedResponse[UserResponse], dependencies=[_super])
async def list_users(page: int = 1, per_page: int = 20, db: AsyncSession = Depends(get_db)):
    return await user_service.list_users(db, page, per_page)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    current_user=Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.create_user(db, data, current_user)
    return UserResponse(
        id=user.id, username=user.username, full_name=user.full_name,
        email=user.email, role=user.role.name, role_id=user.role_id,
        branch=user.branch.name if user.branch else None,
        branch_id=user.branch_id, is_active=user.is_active,
        last_login=user.last_login, created_at=user.created_at,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID, data: UserUpdate,
    current_user=Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_user(db, user_id, data, current_user)
    return UserResponse(
        id=user.id, username=user.username, full_name=user.full_name,
        email=user.email, role=user.role.name, role_id=user.role_id,
        branch=user.branch.name if user.branch else None,
        branch_id=user.branch_id, is_active=user.is_active,
        last_login=user.last_login, created_at=user.created_at,
    )


@router.post("/{user_id}/unlock", response_model=MessageResponse)
async def unlock_user(
    user_id: UUID,
    current_user=Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.user_repo import user_repo
    await user_repo.update(db, user_id, {"locked_until": None, "failed_login_attempts": 0})
    await db.commit()
    return {"message": "Akaunti imefunguliwa"}


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: UUID,
    current_user=Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    await user_service.deactivate_user(db, user_id, current_user)
    return {"message": "Mtumiaji amezimwa"}
