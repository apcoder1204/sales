from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_users(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> tuple[list[User], int]:
        from sqlalchemy import func
        count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        rows = (await db.execute(
            select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count


user_repo = UserRepository()
