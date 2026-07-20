import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
import app.db.base  # noqa — registers all models in SQLAlchemy's mapper registry
from app.api.v1.router import api_router
from app.core.middleware import RequestIDMiddleware, AccessLogMiddleware, SecurityHeadersMiddleware
from app.core.exceptions import AppException

logger = logging.getLogger("dukani.errors")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.ENABLE_HSTS)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    logger.error(f"Unhandled exception [request_id={request_id}]", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Imetokea hitilafu. Jaribu tena.", "code": "INTERNAL_ERROR"},
        headers={"X-Request-ID": request_id},
    )


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
