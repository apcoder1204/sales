"""Reconciliation (Upatanisho wa Hesabu, spec §8). A run crosses branches,
so only the global roles see it; only admins change an exception's status."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.db.session import get_db
from app.schemas.reconciliation import ExceptionOut, RunCreate, RunDetailOut, RunOut, StatusChange
from app.services import reconciliation_service

router = APIRouter(prefix="/reconciliation", tags=["Upatanisho"])

require_recon_reader = require_role("super_admin", "admin", "general_manager")
require_recon_resolver = require_role("super_admin", "admin")


@router.post("/runs", response_model=RunOut, status_code=201)
async def start_run(data: RunCreate, current_user=Depends(require_recon_reader), db: AsyncSession = Depends(get_db)):
    return reconciliation_service.run_out(await reconciliation_service.run(db, data, current_user))


@router.get("/runs", response_model=list[RunOut])
async def list_runs(current_user=Depends(require_recon_reader), db: AsyncSession = Depends(get_db)):
    return [reconciliation_service.run_out(r) for r in await reconciliation_service.list_runs(db)]


@router.get("/runs/{run_id}", response_model=RunDetailOut)
async def get_run(run_id: UUID, current_user=Depends(require_recon_reader), db: AsyncSession = Depends(get_db)):
    return await reconciliation_service.run_detail(db, run_id)


def parse_status(status: str | None) -> list[str] | None:
    """None → live exceptions; "all" → every status; else a comma list."""
    if status is None or not status.strip():
        return None
    if status.strip().lower() == "all":
        return []
    return [x.strip().upper() for x in status.split(",") if x.strip()]


@router.get("/exceptions", response_model=list[ExceptionOut])
async def list_exceptions(
    status: str | None = Query(None), code: str | None = None, branch_id: UUID | None = None,
    run_id: UUID | None = None,
    current_user=Depends(require_recon_reader), db: AsyncSession = Depends(get_db),
):
    rows = await reconciliation_service.list_exceptions(db, parse_status(status), code, branch_id, run_id)
    return [reconciliation_service.exception_out(e) for e in rows]


@router.post("/exceptions/{exception_id}/status", response_model=ExceptionOut)
async def change_status(
    exception_id: UUID, data: StatusChange,
    current_user=Depends(require_recon_resolver), db: AsyncSession = Depends(get_db),
):
    e = await reconciliation_service.change_status(db, exception_id, data, current_user)
    return reconciliation_service.exception_out(e)
