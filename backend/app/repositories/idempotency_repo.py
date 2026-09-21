from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.idempotency_key import IdempotencyKey
from app.repositories.base import BaseRepository


class IdempotencyRepository(BaseRepository[IdempotencyKey]):
    model = IdempotencyKey

    async def get(self, db: AsyncSession, user_id: UUID, endpoint: str, key: str) -> IdempotencyKey | None:
        result = await db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.key == key,
            )
        )
        return result.scalar_one_or_none()


idempotency_repo = IdempotencyRepository()
