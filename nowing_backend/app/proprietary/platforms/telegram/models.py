"""Database models for Telegram Scraper subsystem (Story 22.1 / AD-2, AD-3, AD-5, AD-6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base, TimestampMixin


class TelegramChannel(Base, TimestampMixin):
    """Stores metadata of tracked public and private Telegram channels/supergroups (AD-2)."""

    __tablename__ = "telegram_channels"

    id = Column(BigInteger, primary_key=True, index=True)  # Telegram peer ID
    username = Column(
        String(255), index=True, nullable=True
    )  # Canonical username without @
    title = Column(Text, nullable=False)
    about = Column(Text, nullable=True)
    is_megagroup = Column(Boolean, default=False, server_default=sa_text("false"))
    members_count = Column(Integer, default=0, server_default=sa_text("0"))
    last_scraped_message_id = Column(BigInteger, default=0, server_default=sa_text("0"))
    is_active = Column(Boolean, default=True, server_default=sa_text("true"))

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
    )

    messages = relationship(
        "TelegramMessage",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Compatibility aliases
    @property
    def description(self) -> str | None:
        return self.about

    @description.setter
    def description(self, value: str | None) -> None:
        self.about = value

    @property
    def subscribers_count(self) -> int:
        return self.members_count or 0

    @subscribers_count.setter
    def subscribers_count(self, value: int) -> None:
        self.members_count = value

    @property
    def is_public(self) -> bool:
        return self.is_active

    @is_public.setter
    def is_public(self, value: bool) -> None:
        self.is_active = value

    __table_args__ = (
        Index("idx_telegram_channels_username", "username"),
        Index("idx_telegram_channels_updated_at", "updated_at"),
        {"extend_existing": True},
    )


class TelegramMessage(Base, TimestampMixin):
    """Stores scraped Telegram messages with NLP entities, intent tags, and pgvector embeddings (AD-2, AD-3, AD-4)."""

    __tablename__ = "telegram_messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    channel_id = Column(
        BigInteger,
        ForeignKey("telegram_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(BigInteger, nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    text = Column(Text, nullable=True)
    raw_entities = Column(JSONB, default=list, server_default=sa_text("'[]'::jsonb"))
    author_user_id = Column(BigInteger, nullable=True)
    author_username = Column(String(255), nullable=True)
    views = Column(Integer, default=0, server_default=sa_text("0"))
    forwards = Column(Integer, default=0, server_default=sa_text("0"))
    replies_count = Column(Integer, default=0, server_default=sa_text("0"))
    grouped_id = Column(BigInteger, nullable=True)
    has_media = Column(Boolean, default=False, server_default=sa_text("false"))
    intent_tag = Column(
        String(50), nullable=True, index=True
    )  # 'sell', 'buy', 'seeking', 'news'
    embedding = Column(Vector(1536), nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=sa_text("now()"),
    )

    channel = relationship("TelegramChannel", back_populates="messages")
    media = relationship(
        "TelegramMedia",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Compatibility aliases
    @property
    def published_at(self) -> datetime:
        return self.date

    @published_at.setter
    def published_at(self, value: datetime) -> None:
        self.date = value

    @property
    def text_content(self) -> str | None:
        return self.text

    @text_content.setter
    def text_content(self, value: str | None) -> None:
        self.text = value

    @property
    def views_count(self) -> int:
        return self.views or 0

    @views_count.setter
    def views_count(self, value: int) -> None:
        self.views = value

    @property
    def forwards_count(self) -> int:
        return self.forwards or 0

    @forwards_count.setter
    def forwards_count(self, value: int) -> None:
        self.forwards = value

    @property
    def author_name(self) -> str | None:
        return self.author_username

    @author_name.setter
    def author_name(self, value: str | None) -> None:
        self.author_username = value

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "message_id", name="uq_telegram_channel_message"
        ),
        Index("idx_telegram_messages_channel_date", "channel_id", "date"),
        Index(
            "idx_telegram_messages_entities_gin", "raw_entities", postgresql_using="gin"
        ),
        Index("idx_telegram_msg_intent", "intent_tag"),
        {"extend_existing": True},
    )


class TelegramMedia(Base, TimestampMixin):
    """Stores metadata and S3 blob links for media files attached to Telegram messages (AD-5)."""

    __tablename__ = "telegram_media"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("telegram_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_type = Column(
        String(50), nullable=False
    )  # 'photo', 'video', 'document', 'audio'
    file_id = Column(Text, nullable=False)
    file_name = Column(Text, nullable=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, default=0, server_default=sa_text("0"))
    storage_url = Column(Text, nullable=True)
    upload_status = Column(
        String(50), default="pending", server_default=sa_text("'pending'")
    )

    message = relationship("TelegramMessage", back_populates="media")

    # Compatibility aliases
    @property
    def file_url(self) -> str | None:
        return self.storage_url or self.file_id

    @file_url.setter
    def file_url(self, value: str | None) -> None:
        self.storage_url = value

    @property
    def file_size_bytes(self) -> int:
        return self.size_bytes or 0

    @file_size_bytes.setter
    def file_size_bytes(self, value: int) -> None:
        self.size_bytes = value

    __table_args__ = (
        Index("idx_telegram_media_message_id", "message_id"),
        Index("idx_telegram_media_status", "upload_status"),
        {"extend_existing": True},
    )
