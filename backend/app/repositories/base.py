from uuid import UUID
from typing import Generic, TypeVar, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.exceptions import NotFoundException

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: Type[ModelT]

    async def get_by_id(self, db: AsyncSession, id: UUID) -> ModelT | None:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> tuple[list[ModelT], int]:
        count_result = await db.execute(select(func.count()).select_from(self.model))
        total = count_result.scalar_one()
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all(), total

    async def create(self, db: AsyncSession, data: dict) -> ModelT:
        instance = self.model(**data)
        db.add(instance)
        await db.flush()
        await db.refresh(instance)
        return instance

    async def update(self, db: AsyncSession, id: UUID, data: dict) -> ModelT:
        instance = await self.get_by_id(db, id)
        if not instance:
            raise NotFoundException()
        for k, v in data.items():
            setattr(instance, k, v)
        await db.flush()
        await db.refresh(instance)
        return instance
