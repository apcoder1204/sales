import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, ForeignKey, Enum as SAEnum, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100))
    family_name: Mapped[str | None] = mapped_column(String(100))
    family_id: Mapped[str | None] = mapped_column(String(50))
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="Kipande")
    description: Mapped[str | None] = mapped_column(Text)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    minimum_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(
        SAEnum("active", "inactive", "discontinued", name="product_status_enum"),
        nullable=False, default="active"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    category: Mapped["Category"] = relationship("Category", lazy="selectin")
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by], lazy="noload")

    __table_args__ = (
        CheckConstraint("cost_price >= 0", name="chk_products_cost_positive"),
        CheckConstraint("selling_price >= 0", name="chk_products_price_positive"),
        CheckConstraint("minimum_stock >= 0", name="chk_products_min_stock"),
    )
