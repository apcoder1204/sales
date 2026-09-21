import asyncio
import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from app.config import settings
import app.db.base  # noqa — registers all models in SQLAlchemy's mapper registry
from app.api.v1.router import api_router
from app.core.middleware import RequestIDMiddleware, AccessLogMiddleware, SecurityHeadersMiddleware
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.db.session import engine

logger = logging.getLogger("dukani.errors")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.state.limiter = limiter

app.add_middleware(GZipMiddleware, minimum_size=1000)
# Added before CORSMiddleware so it ends up *inner* to it — CORS handles
# preflight OPTIONS requests and short-circuits them before they'd otherwise
# count against a client's rate limit.
app.add_middleware(SlowAPIMiddleware)
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


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    response = JSONResponse(
        status_code=429,
        content={
            "detail": "Umefanya majaribio mengi. Tafadhali subiri kisha jaribu tena.",
            "code": "RATE_LIMIT_EXCEEDED",
        },
    )
    return limiter._inject_headers(response, request.state.view_rate_limit)


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
    # A 200 here previously only proved the FastAPI process was alive — the
    # most likely real failure (DB unreachable, pool exhausted, disk full)
    # was invisible to it. That gap let the NoNewPrivileges webhook bug ship
    # unnoticed for two days: the old health check kept passing against a
    # stale process the whole time. A short-timeout SELECT 1 catches that
    # class of failure instead of just "the process didn't crash".
    db_status = "ok"
    db_latency_ms = None
    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=3)
        db_latency_ms = round((time.monotonic() - start) * 1000, 1)
    except Exception:
        db_status = "unreachable"

    pool = engine.pool
    body = {
        "status": "healthy" if db_status == "ok" else "unhealthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
            "pool_size": pool.size(),
            "pool_checked_out": pool.checkedout(),
            "pool_overflow": pool.overflow(),
        },
    }
    return JSONResponse(status_code=200 if db_status == "ok" else 503, content=body)
