from fastapi import APIRouter
from app.api.v1 import auth, users, products, inventory, sales, transfers, reports, audit_logs, daily_closing, branches, whatsapp, customers, payments, opening_balances, receivables, debt_reports

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(branches.router)
api_router.include_router(products.router)
api_router.include_router(inventory.router)
api_router.include_router(sales.router)
api_router.include_router(transfers.router)
api_router.include_router(reports.router)
api_router.include_router(audit_logs.router)
api_router.include_router(daily_closing.router)
api_router.include_router(whatsapp.router)
api_router.include_router(customers.router)
api_router.include_router(payments.router)
api_router.include_router(opening_balances.router)
api_router.include_router(receivables.router)
api_router.include_router(debt_reports.router)
