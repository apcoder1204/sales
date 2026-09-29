from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.schemas.branch import BranchCreate, BranchUpdate, BranchResponse
from app.services.branch_service import branch_service

# Global branch REGISTRY management — deliberately separate from
# GET /users/branches, which returns the branch-context *selector* list
# (scoped per role via get_authorized_branches, used by every role to pick
# their working branch). This router is the actual system-of-record CRUD
# surface for the branches table, and every route here requires
# super_admin or admin — enforced by require_admin, the same dependency
# every other admin-only surface in this app already uses. A branch
# selector is not branch-management permission; the two are kept
# structurally distinct on purpose.
router = APIRouter(prefix="/branches", tags=["Matawi"])


@router.get("", response_model=list[BranchResponse], dependencies=[Depends(require_admin)])
async def list_branches(db: AsyncSession = Depends(get_db)):
    return await branch_service.list_branches(db)


@router.get("/{branch_id}", response_model=BranchResponse, dependencies=[Depends(require_admin)])
async def get_branch(branch_id: UUID, db: AsyncSession = Depends(get_db)):
    return await branch_service.get_branch(db, branch_id)


@router.post("", response_model=BranchResponse, status_code=201)
async def create_branch(
    data: BranchCreate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await branch_service.create_branch(db, data, current_user)


@router.patch("/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: UUID, data: BranchUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await branch_service.update_branch(db, branch_id, data, current_user)


@router.delete("/{branch_id}")
async def delete_branch(
    branch_id: UUID,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await branch_service.delete_branch(db, branch_id, current_user)
