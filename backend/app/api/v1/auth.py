from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserProfile
from app.schemas.common import MessageResponse
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Uthibitisho"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    return await auth_service.login(db, data.username, data.password, ip)


@router.post("/refresh")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_token(db, data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await audit_service.log(
        db, action="USER_LOGOUT", category="authentication",
        user_id=current_user.id, username=current_user.username,
        user_role=current_user.role.name,
    )
    return {"message": "Umetoka mfumoni"}


@router.get("/me", response_model=UserProfile)
async def me(current_user=Depends(get_current_user)):
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role.name,
        branch_id=current_user.branch_id,
        branch=current_user.branch.name if current_user.branch else None,
    )
