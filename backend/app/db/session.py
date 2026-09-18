from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    # Every timestamp column in this schema is TIMESTAMPTZ, and every
    # app-computed timestamp (the `_utcnow()` convention used throughout —
    # datetime.now(UTC) with tzinfo stripped) is a *naive* value meant to be
    # interpreted as UTC. asyncpg/Postgres interpret a naive value against a
    # TIMESTAMPTZ column using the session's `TimeZone` setting, which
    # otherwise defaults to the server's zone (Africa/Dar_es_Salaam, UTC+3)
    # — silently shifting every naive-datetime write or comparison by 3
    # hours. Forcing UTC here makes the DB session agree with the
    # convention every naive timestamp in this codebase already assumes.
    connect_args={"server_settings": {"timezone": "UTC"}},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
