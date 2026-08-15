"""Add telegram_channels, telegram_messages, and telegram_media tables (Story 22.1 / AD-2, AD-3, AD-5).

Revision ID: 210
Revises: 209
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "210"
down_revision: str | None = "209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. telegram_channels
    op.create_table(
        "telegram_channels",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("peer_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("is_megagroup", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("members_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_scraped_message_id", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_telegram_channels_username",
        "telegram_channels",
        ["username"],
        unique=True,
    )
    op.create_index(
        "idx_telegram_channels_peer_id",
        "telegram_channels",
        ["peer_id"],
        unique=True,
    )
    op.create_index(
        "idx_telegram_channels_updated_at",
        "telegram_channels",
        ["updated_at"],
    )

    # 2. telegram_messages
    op.create_table(
        "telegram_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("telegram_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("raw_entities", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("author_username", sa.String(length=255), nullable=True),
        sa.Column("views", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("forwards", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("replies_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("grouped_id", sa.BigInteger(), nullable=True),
        sa.Column("has_media", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("intent_tag", sa.String(length=50), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("channel_id", "message_id", name="uq_telegram_channel_message"),
    )
    op.create_index("idx_telegram_messages_channel_id", "telegram_messages", ["channel_id"])
    op.create_index("idx_telegram_messages_channel_date", "telegram_messages", ["channel_id", "date"])
    op.create_index(
        "idx_telegram_messages_entities_gin",
        "telegram_messages",
        ["raw_entities"],
        postgresql_using="gin",
    )
    op.create_index("idx_telegram_msg_intent", "telegram_messages", ["intent_tag"])

    # PostgreSQL HNSW vector index
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_telegram_msg_embedding ON telegram_messages "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);"
        )
    )
    # PostgreSQL GIN full-text search index
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_telegram_msg_text_gin ON telegram_messages "
            "USING gin (to_tsvector('simple', COALESCE(text, '')));"
        )
    )

    # 3. telegram_media
    op.create_table(
        "telegram_media",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("telegram_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_type", sa.String(length=50), nullable=False),
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("upload_status", sa.String(length=50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_telegram_media_message_id", "telegram_media", ["message_id"])
    op.create_index("idx_telegram_media_status", "telegram_media", ["upload_status"])


def downgrade() -> None:
    op.drop_table("telegram_media")
    op.execute(sa.text("DROP INDEX IF EXISTS idx_telegram_msg_embedding;"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_telegram_msg_text_gin;"))
    op.drop_table("telegram_messages")
    op.drop_table("telegram_channels")
