"""Models for the presentations domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.config import config
from app.db.base import Base, BaseModel, TimestampMixin
from app.db.enums import MeetingMinutesStatus, VideoPresentationStatus


class VideoPresentation(BaseModel, TimestampMixin):
    """Video presentation model for storing AI-generated video presentations.

    The slides JSONB stores per-slide data including Remotion component code,
    audio file paths, and durations. The frontend compiles the code and renders
    the video using Remotion Player.
    """

    __tablename__ = "video_presentations"

    title = Column(String(500), nullable=False)
    slides = Column(JSONB, nullable=True)
    scene_codes = Column(JSONB, nullable=True)
    status = Column(
        SQLAlchemyEnum(
            VideoPresentationStatus,
            name="video_presentation_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=VideoPresentationStatus.READY,
        server_default="ready",
        index=True,
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="video_presentations")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")


class MeetingMinutes(BaseModel, TimestampMixin):
    """Meeting minutes model for storing AI-generated meeting minutes."""

    __tablename__ = "meeting_minutes"

    title = Column(String(500), nullable=True)
    status = Column(
        SQLAlchemyEnum(
            MeetingMinutesStatus,
            name="meeting_minutes_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=MeetingMinutesStatus.PENDING,
        server_default="pending",
        index=True,
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace = relationship("Workspace", back_populates="meeting_minutes")

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    user = relationship("User")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document = relationship("Document")

    audio_source_url = Column(Text, nullable=True)
    processing_task_id = Column(String(255), nullable=True, index=True)

    transcript = Column(JSONB, nullable=True, default=list)
    action_items = Column(JSONB, nullable=True, default=list)
    summary = Column(Text, nullable=True)
    raw_transcript = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    meeting_metadata = Column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )


class Report(BaseModel, TimestampMixin):
    """Report model for storing generated reports (Markdown or Typst)."""

    __tablename__ = "reports"

    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    content_type = Column(String(20), nullable=False, server_default="markdown")
    report_metadata = Column(JSONB, nullable=True)  # section headings, word count, etc.
    report_style = Column(
        String(100), nullable=True
    )  # e.g. "executive_summary", "deep_research"

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="reports")

    # Versioning: reports sharing the same report_group_id are versions of the same report.
    # For v1, report_group_id = the report's own id (set after insert).
    report_group_id = Column(Integer, nullable=True, index=True)

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")


class SlidePresentation(Base):
    """Generated PPTX or Marp Markdown slide deck for a workspace (Story 27.2a)."""

    __tablename__ = "slide_presentations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", name="uq_slide_presentations_workspace_slug"
        ),
        Index("ix_slide_presentations_workspace_status", "workspace_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    slug = Column(String(63), nullable=False, index=True)
    format = Column(String(10), nullable=False, default="pptx")
    status = Column(
        String(50),
        nullable=False,
        default="generating",
        server_default=text("'generating'"),
    )  # generating, ready, failed, degraded, validation_failed
    file_path = Column(String(512), nullable=True)
    preview_url = Column(String(512), nullable=True)
    slide_count = Column(Integer, nullable=True)
    degradation_reason = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    @property
    def download_url(self) -> str | None:
        """Public download URL for the generated deck."""
        if not self.file_path:
            return None
        return (
            f"{config.BACKEND_URL.rstrip('/')}/api/v1/presentations/{self.id}"
            f"/download?workspace_id={self.workspace_id}"
        )

    workspace = relationship("Workspace", backref="slide_presentations")
    user = relationship("User", backref="slide_presentations")
