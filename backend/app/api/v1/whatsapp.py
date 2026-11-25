from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import require_admin, require_role
from app.db.session import get_db
from app.schemas.whatsapp import (
    WhatsAppSettingsResponse,
    WhatsAppSettingsUpdate,
    WhatsAppStatusResponse,
)
from app.services import whatsapp_service
from app.services.whatsapp_gateway import WhatsAppGateway, get_whatsapp_gateway

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

_any_report_reader = Depends(
    require_role("super_admin", "admin", "general_manager", "store_keeper", "cashier")
)


async def _is_connected(gateway: WhatsAppGateway) -> bool:
    if not settings.WHATSAPP_ENABLED:
        return False
    return await gateway.session_status() == "ready"


async def _settings_response(db: AsyncSession, gateway: WhatsAppGateway) -> WhatsAppSettingsResponse:
    number, locked = await whatsapp_service.get_receiver(db)
    return WhatsAppSettingsResponse(
        number=number, locked=locked, enabled=settings.WHATSAPP_ENABLED,
        connected=await _is_connected(gateway),
    )


@router.get("/status", response_model=WhatsAppStatusResponse, dependencies=[_any_report_reader])
async def get_status(
    db: AsyncSession = Depends(get_db),
    gateway: WhatsAppGateway = Depends(get_whatsapp_gateway),
):
    number, _ = await whatsapp_service.get_receiver(db)
    return WhatsAppStatusResponse(
        enabled=settings.WHATSAPP_ENABLED,
        configured=number is not None,
        connected=await _is_connected(gateway),
    )


@router.get("/settings", response_model=WhatsAppSettingsResponse, dependencies=[Depends(require_admin)])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    gateway: WhatsAppGateway = Depends(get_whatsapp_gateway),
):
    return await _settings_response(db, gateway)


@router.put("/settings", response_model=WhatsAppSettingsResponse)
async def update_settings(
    data: WhatsAppSettingsUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    gateway: WhatsAppGateway = Depends(get_whatsapp_gateway),
):
    await whatsapp_service.set_receiver(db, data.number, current_user)
    return await _settings_response(db, gateway)
