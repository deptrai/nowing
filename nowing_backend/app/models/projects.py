"""Models for the projects and modular skills hub domain."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
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

from app.db.base import BaseModel, TimestampMixin


class Project(BaseModel, TimestampMixin):
    """
    Project model representing a persistent domain workspace within a workspace.
    Contains master instructions, pinned documents, and linked skills.
    """

    __tablename__ = "projects"

    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    master_instructions = Column(Text, nullable=True)
    is_archived = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
        index=True,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="projects")
    created_by = relationship("User", foreign_keys=[created_by_id])
    pinned_documents = relationship(
        "ProjectPinnedDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectPinnedDocument.pinned_at.desc()",
    )
    project_skills = relationship(
        "ProjectSkill",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    new_chat_threads = relationship(
        "NewChatThread",
        back_populates="project",
        foreign_keys="[NewChatThread.project_id]",
    )


class ProjectPinnedDocument(BaseModel):
    """
    Link table connecting projects with pinned workspace documents.
    """

    __tablename__ = "project_pinned_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "document_id", name="uq_project_pinned_document"),
        Index("ix_project_pinned_documents_project_id", "project_id"),
        Index("ix_project_pinned_documents_document_id", "document_id"),
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    pinned_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        index=True,
    )

    # Relationships
    project = relationship("Project", back_populates="pinned_documents")
    document = relationship("Document")


class WorkspaceSkill(BaseModel, TimestampMixin):
    """
    Skill model for modular .skill.md definitions registered in a workspace.
    """

    __tablename__ = "workspace_skills"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_workspace_skills_workspace_slug"),
        Index("ix_workspace_skills_workspace_id", "workspace_id"),
        Index("ix_workspace_skills_slug", "slug"),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    trigger_pattern = Column(String(255), nullable=False)
    content_markdown = Column(Text, nullable=False)
    skill_type = Column(
        String(50), nullable=False, default="prompt", server_default="prompt"
    )
    parameters_schema = Column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("now()"),
        index=True,
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="skills")
    created_by = relationship("User", foreign_keys=[created_by_id])
    project_skills = relationship(
        "ProjectSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class ProjectSkill(BaseModel):
    """
    Link table connecting projects with workspace skills.
    """

    __tablename__ = "project_skills"
    __table_args__ = (
        UniqueConstraint("project_id", "skill_id", name="uq_project_skills_project_skill"),
        Index("ix_project_skills_project_id", "project_id"),
        Index("ix_project_skills_skill_id", "skill_id"),
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_id = Column(
        Integer,
        ForeignKey("workspace_skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Relationships
    project = relationship("Project", back_populates="project_skills")
    skill = relationship("WorkspaceSkill", back_populates="project_skills")
