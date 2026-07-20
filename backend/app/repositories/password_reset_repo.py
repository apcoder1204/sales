from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.password_reset_token import PasswordResetToken
from app.repositories.base import BaseRepository

UTC = timezone.utc


class PasswordResetRepository(BaseRepository[PasswordResetToken]):
    model = PasswordResetToken

    async def get_valid_by_hash(self, db: AsyncSession, token_hash: str) -> PasswordResetToken | None:
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()


password_reset_repo = PasswordResetRepository()
