"""Models for the scraper domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
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
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, BaseModel, TimestampMixin


class ScraperPlatformAccount(Base, TimestampMixin):
    """Admin-managed credentials for a proprietary scraper platform."""

    __tablename__ = "scraper_platform_accounts"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(64), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    encrypted_credentials = Column(Text, nullable=True)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    usage_state = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    __table_args__ = (
        Index(
            "uq_scraper_platform_accounts_default",
            "platform",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )


class ScraperRule(Base, TimestampMixin):
    """Versioned, admin-managed rule schema for a scraper platform."""

    __tablename__ = "scraper_rules"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    rule_schema = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "platform", "version", name="uq_scraper_rules_platform_version"
        ),
        Index(
            "uq_scraper_rules_active_per_platform",
            "platform",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )


class Run(Base, TimestampMixin):
    """One row per scraper-capability invocation, from either the agent door
    or the REST/API-key door.

    Backs the user-facing Scraper-API logs and the agent's tool-boundary
    truncation: the full output lives here while the model sees only a capped
    preview plus this row's id. ``output_text`` is stored as JSONL (one item
    per line, ``exclude_none``) so ``read_run``/``search_run`` can page and grep
    by line without parsing the whole payload. Retained ~30 days via opportunistic
    bounded cleanup on insert.

    ``cost_micros`` ships nullable and unpopulated in this pass; the planned
    per-verb pricing rework will fill it. ``thread_id`` is a free-form string
    (subagent ids look like ``"2099::task:call_x"``), so it is intentionally not
    a foreign key.
    """

    __tablename__ = "runs"
    __allow_unmapped__ = True

    __table_args__ = (
        Index("ix_runs_workspace_created", "workspace_id", "created_at"),
        # AC-18.7: vertical-client run attribution and daily rollups.
        Index(
            "ix_runs_workspace_client_created",
            "workspace_id",
            "client_id",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    thread_id = Column(String(255), nullable=True)
    capability = Column(String(100), nullable=False, index=True)
    origin = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    error = Column(Text, nullable=True)
    input = Column(JSONB, nullable=True)
    output_text = Column(Text, nullable=True)
    item_count = Column(Integer, nullable=False, default=0)
    char_count = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=True)
    cost_micros = Column(BigInteger, nullable=True)
    client_id = Column(Text, nullable=True, index=True)
    external_metadata = Column(JSONB, nullable=True, default=dict)
    # Coarse progress log (list of throttled events) captured during the run;
    # the live fine-grained stream is ephemeral (bus/SSE only).
    progress = Column(JSONB, nullable=True)
    # Durable memory-extraction state (Story 3.13, D6). Celery delivery is
    # at-least-once, so idempotency cannot rely on "did this run produce
    # memory rows" alone: a successful extraction that found ZERO qualifying
    # facts must also be terminal, or every redelivery re-calls (and re-pays
    # for) the LLM. ``pending`` is claimed via compare-and-set before the LLM
    # call so two concurrent workers resolve to exactly one LLM call.
    #   NULL      -> never enqueued/considered
    #   pending   -> claimed by a worker, LLM call in flight
    #   completed -> extraction ran to completion (with or without facts)
    #   skipped   -> policy/gate/missing-creator decision, terminal
    #   failed    -> retry budget exhausted, terminal
    memory_extraction_status = Column(String(16), nullable=True, index=True)
    memory_extraction_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Structured skip/failure reason, sharing Story 8.7/8.8's vocabulary
    # (``disabled``, ``anonymous_unbilled``, ``missing_creator``, ...).
    memory_extraction_skip_reason = Column(String(64), nullable=True)


class AntiBotEscalation(BaseModel, TimestampMixin):
    """Admin-escalation row for an anti-bot / CAPTCHA block.

    Tracks which workspace and capability hit a block, how many times the same
    (workspace, domain, capability) tripped while open, and the screenshot
    evidence. Open rows are grouped by (workspace_id, domain, capability) so
    repeated blocks increment ``detection_count`` rather than creating noise.
    """

    __tablename__ = "anti_bot_escalations"

    __table_args__ = (
        Index(
            "ix_anti_bot_escalations_grouping_open_unique",
            "workspace_id",
            "domain",
            "capability",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "ix_anti_bot_escalations_status_created_at",
            "status",
            "created_at",
        ),
    )

    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capability = Column(String(100), nullable=False)
    domain = Column(String(500), nullable=False)
    block_type = Column(String(50), nullable=False)
    screenshot_url = Column(String(2048), nullable=True)
    status = Column(
        ENUM("open", "resolved", "retry", name="anti_bot_escalation_status"),
        nullable=False,
        default="open",
        server_default="open",
    )
    detection_count = Column(Integer, nullable=False, default=1, server_default="1")
    last_seen_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # ``metadata`` is a reserved name on ``Base``, so the Python attribute is
    # ``escalation_metadata`` while the database column keeps the requested
    # ``metadata`` name.
    escalation_metadata = Column("metadata", JSONB, nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    run = relationship("Run")
    workspace = relationship("Workspace")


class ToolOutputSpill(Base, TimestampMixin):
    """Internal scratch store for main-agent context-editing spills.

    Kept separate from ``runs`` so customer-facing scraper logs stay clean.
    The full ``ToolMessage`` content that context editing evicts is written here
    and the message body is replaced with a ``spill_{id}`` placeholder the agent
    can read back via ``read_run``/``search_run``. Retained ~7 days.
    """

    __tablename__ = "tool_output_spills"
    __allow_unmapped__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    thread_id = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
