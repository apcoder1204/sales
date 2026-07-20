from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.dependencies import require_admin, get_current_user
from app.schemas.user import UserCreate, UserUpdate, UserResponse, RoleResponse
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.user_service import user_service, HIDDEN_FROM_ADMIN

router = APIRouter(prefix="/users", tags=["Watumiaji"])


@router.get("/branches")
async def list_branches(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.branch import Branch
    rows = (await db.execute(select(Branch).where(Branch.is_active == True).order_by(Branch.name))).scalars().all()
    return [{"id": str(b.id), "name": b.name, "code": b.code, "branch_type": b.branch_type} for b in rows]


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from app.models.role import Role
    rows = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
    if current_user.role.name == "admin":
        rows = [r for r in rows if r.name not in HIDDEN_FROM_ADMIN]
    return rows


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = 1, per_page: int = 20,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.list_users(db, page, per_page, current_user)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    current_user=Depends(require_admin),
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
    current_user=Depends(require_admin),
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
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_service.unlock_user(db, user_id, current_user)
    return {"message": "Akaunti imefunguliwa"}


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: UUID,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_service.deactivate_user(db, user_id, current_user)
    return {"message": "Mtumiaji amezimwa"}
