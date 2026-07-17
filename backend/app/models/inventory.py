import uuid
from datetime import datetime
from sqlalchemy import Integer, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship("Product", lazy="selectin")
    branch: Mapped["Branch"] = relationship("Branch", lazy="selectin")

    @property
    def available_qty(self) -> int:
        return self.quantity - self.reserved_qty

    __table_args__ = (
        UniqueConstraint("product_id", "branch_id", name="uq_inventory_product_branch"),
        CheckConstraint("quantity >= 0", name="chk_inventory_qty_non_negative"),
        CheckConstraint("reserved_qty >= 0", name="chk_inventory_reserved_pos"),
        CheckConstraint("reserved_qty <= quantity", name="chk_inventory_reserved_lte_qty"),
    )
