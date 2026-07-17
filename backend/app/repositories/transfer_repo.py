from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models.stock_request import StockRequest
from app.models.stock_request_item import StockRequestItem
from app.models.stock_transfer import StockTransfer
from app.models.stock_transfer_item import StockTransferItem
from app.repositories.base import BaseRepository


class TransferRepository(BaseRepository[StockTransfer]):
    model = StockTransfer

    async def get_next_request_no(self, db: AsyncSession) -> str:
        result = await db.execute(text("SELECT nextval('seq_request_number')"))
        seq = result.scalar()
        today = datetime.now().strftime("%Y%m%d")
        return f"REQ-{today}-{seq:04d}"

    async def get_next_transfer_no(self, db: AsyncSession) -> str:
        result = await db.execute(text("SELECT nextval('seq_transfer_number')"))
        seq = result.scalar()
        today = datetime.now().strftime("%Y%m%d")
        return f"TRF-{today}-{seq:04d}"

    async def create_request(self, db: AsyncSession, data: dict) -> StockRequest:
        req = StockRequest(**data)
        db.add(req)
        await db.flush()
        await db.refresh(req)
        return req

    async def create_request_item(self, db: AsyncSession, data: dict) -> StockRequestItem:
        item = StockRequestItem(**data)
        db.add(item)
        await db.flush()
        return item

    async def get_request_by_id(self, db: AsyncSession, id: UUID) -> StockRequest | None:
        result = await db.execute(select(StockRequest).where(StockRequest.id == id))
        return result.scalar_one_or_none()

    async def get_request_item_by_id(self, db: AsyncSession, id: UUID) -> StockRequestItem | None:
        result = await db.execute(select(StockRequestItem).where(StockRequestItem.id == id))
        return result.scalar_one_or_none()

    async def list_requests(
        self, db: AsyncSession,
        status: str | None = None,
        branch_id: UUID | None = None,
        skip: int = 0, limit: int = 20
    ) -> tuple[list[StockRequest], int]:
        q = select(StockRequest)
        if status:
            q = q.where(StockRequest.status == status)
        if branch_id:
            q = q.where(
                (StockRequest.from_branch_id == branch_id) |
                (StockRequest.to_branch_id == branch_id)
            )
        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await db.execute(
            q.order_by(StockRequest.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count

    async def list_transfers(
        self, db: AsyncSession,
        from_branch_id: UUID | None = None,
        to_branch_id: UUID | None = None,
        skip: int = 0, limit: int = 20
    ) -> tuple[list[StockTransfer], int]:
        q = select(StockTransfer)
        if from_branch_id:
            q = q.where(StockTransfer.from_branch_id == from_branch_id)
        if to_branch_id:
            q = q.where(StockTransfer.to_branch_id == to_branch_id)
        count = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
        rows = (await db.execute(
            q.order_by(StockTransfer.created_at.desc()).offset(skip).limit(limit)
        )).scalars().all()
        return rows, count

    async def create_transfer(self, db: AsyncSession, data: dict) -> StockTransfer:
        tf = StockTransfer(**data)
        db.add(tf)
        await db.flush()
        return tf

    async def create_transfer_item(self, db: AsyncSession, data: dict) -> StockTransferItem:
        item = StockTransferItem(**data)
        db.add(item)
        await db.flush()
        return item


transfer_repo = TransferRepository()
