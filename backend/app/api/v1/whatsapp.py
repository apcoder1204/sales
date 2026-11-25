from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import require_admin
from app.db.session import get_db
from app.schemas.whatsapp import WhatsAppSettingsResponse, WhatsAppSettingsUpdate
from app.services import whatsapp_service

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


async def _settings_response(db: AsyncSession) -> WhatsAppSettingsResponse:
    number, locked = await whatsapp_service.get_receiver(db)
    return WhatsAppSettingsResponse(
        number=number, locked=locked, enabled=settings.WHATSAPP_ENABLED, connected=False
    )


@router.get("/settings", response_model=WhatsAppSettingsResponse, dependencies=[Depends(require_admin)])
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await _settings_response(db)


@router.put("/settings", response_model=WhatsAppSettingsResponse)
async def update_settings(
    data: WhatsAppSettingsUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await whatsapp_service.set_receiver(db, data.number, current_user)
    return await _settings_response(db)
