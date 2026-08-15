"""add ecommerce tables (Story 17.2 / AD-EC-1 to AD-EC-8)

Revision ID: 202
Revises: 003b1d6ea556
Create Date: 2026-08-15 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202"
down_revision: str | None = "003b1d6ea556"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ecommerce_products",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(length=50), nullable=False, server_default="shopee"),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("shop_id", sa.BigInteger(), nullable=False),
        sa.Column("shop_name", sa.Text(), nullable=True),
        sa.Column("shop_location", sa.String(length=100), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("current_price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("original_price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("historical_sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating_star", sa.Numeric(precision=3, scale=2), nullable=True, server_default="0.0"),
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="in_stock"),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("raw_specs", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("platform", "item_id", "shop_id", name="uq_ecommerce_product"),
    )
    op.create_index("idx_ecom_products_item_shop", "ecommerce_products", ["item_id", "shop_id"])
    op.create_index("idx_shopee_product_ext_id", "ecommerce_products", ["platform", "item_id"])

    op.create_table(
        "ecommerce_price_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("ecommerce_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_ecom_price_history_prod", "ecommerce_price_history", ["product_id", "recorded_at"])
    op.create_index("idx_shopee_price_history_product_time", "ecommerce_price_history", ["product_id", "recorded_at"])


def downgrade() -> None:
    op.drop_index("idx_shopee_price_history_product_time", table_name="ecommerce_price_history")
    op.drop_index("idx_ecom_price_history_prod", table_name="ecommerce_price_history")
    op.drop_table("ecommerce_price_history")

    op.drop_index("idx_shopee_product_ext_id", table_name="ecommerce_products")
    op.drop_index("idx_ecom_products_item_shop", table_name="ecommerce_products")
    op.drop_table("ecommerce_products")
