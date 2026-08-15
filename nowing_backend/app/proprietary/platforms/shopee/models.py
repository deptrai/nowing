"""Database models for E-Commerce Intelligence (Story 17.2 / AD-EC-1 to AD-EC-8)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin


class EcommerceProduct(BaseModel, TimestampMixin):
    """Stores normalized products from e-commerce platforms (Shopee, etc.)."""

    __tablename__ = "ecommerce_products"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, default="shopee", server_default="shopee", index=True)
    item_id = Column(BigInteger, nullable=False, index=True)
    shop_id = Column(BigInteger, nullable=False, index=True)

    shop_name = Column(Text, nullable=True)
    shop_location = Column(String(100), nullable=True)
    title = Column(Text, nullable=False)
    brand = Column(String(255), nullable=True)

    current_price = Column(Numeric(18, 2), nullable=False)
    original_price = Column(Numeric(18, 2), nullable=True)
    discount_percent = Column(Integer, default=0, server_default="0")
    historical_sold = Column(Integer, default=0, server_default="0")
    rating_star = Column(Numeric(3, 2), nullable=True, default=0.0)
    rating_count = Column(Integer, default=0, server_default="0")
    stock = Column(Integer, default=0, server_default="0")
    status = Column(String(50), nullable=False, default="in_stock", server_default="in_stock")

    image_url = Column(Text, nullable=True)
    product_url = Column(Text, nullable=True)
    raw_specs = Column(JSONB, default=dict, server_default=text("'{}'::jsonb"))

    price_history = relationship(
        "EcommercePriceHistory",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def name(self) -> str:
        """Alias for title for compatibility."""
        return self.title

    @name.setter
    def name(self, value: str) -> None:
        self.title = value

    @property
    def external_product_id(self) -> str:
        """Alias for external platform product identifier (format: shop_id_item_id)."""
        if self.shop_id:
            return f"{self.shop_id}_{self.item_id}"
        return str(self.item_id)

    __table_args__ = (
        UniqueConstraint("platform", "item_id", "shop_id", name="uq_ecommerce_product"),
        Index("idx_ecom_products_item_shop", "item_id", "shop_id"),
        Index("idx_shopee_product_ext_id", "platform", "item_id"),
    )


class EcommercePriceHistory(BaseModel, TimestampMixin):
    """Stores historical price time-series snapshots for sparkline tracking and price drop alerts."""

    __tablename__ = "ecommerce_price_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(
        BigInteger,
        ForeignKey("ecommerce_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price = Column(Numeric(18, 2), nullable=False)
    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    product = relationship("EcommerceProduct", back_populates="price_history")

    __table_args__ = (
        Index("idx_ecom_price_history_prod", "product_id", "recorded_at"),
    )

