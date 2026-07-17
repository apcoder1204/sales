import uuid
from datetime import datetime
from sqlalchemy import Integer, ForeignKey, Boolean, Text, Enum as SAEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base


class StockRequestItem(Base):
    __tablename__ = "stock_request_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_requests.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    requested_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    main_store_had_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved_qty: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "approved", "rejected", "fulfilled", name="request_status_enum"),
        nullable=False, default="pending"
    )
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column()

    product: Mapped["Product"] = relationship("Product", lazy="selectin")

    __table_args__ = (
        CheckConstraint("requested_qty > 0", name="chk_stock_req_items_qty_pos"),
        CheckConstraint(
            "approved_qty IS NULL OR (approved_qty >= 0 AND approved_qty <= requested_qty)",
            name="chk_stock_req_items_approved_qty",
        ),
    )
