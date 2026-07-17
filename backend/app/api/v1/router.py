from fastapi import APIRouter
from app.api.v1 import auth, users, products, inventory, sales, transfers, reports, audit_logs, daily_closing

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(products.router)
api_router.include_router(inventory.router)
api_router.include_router(sales.router)
api_router.include_router(transfers.router)
api_router.include_router(reports.router)
api_router.include_router(audit_logs.router)
api_router.include_router(daily_closing.router)
