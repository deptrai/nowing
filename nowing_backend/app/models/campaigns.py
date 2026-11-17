"""Persistent lead campaign models (Epic 44.1).

Ba bảng: ``lead_campaigns`` (chiến dịch), ``campaign_runs`` (mỗi lần chạy),
``campaign_leads`` (junction campaign↔lead kèm role). Tên bảng là
``lead_campaigns`` — KHÔNG phải ``campaigns`` vì ``webset_campaigns`` đã
chiếm namespace campaign từ trước.

RLS: cả 3 bảng được bật ENABLE + FORCE ROW LEVEL SECURITY với predicate
chỉ trên ``workspace_id`` (migration 251). Junction ``campaign_leads`` cố
tình KHÔNG có lead-visibility policy (deviation có chủ đích — xem spec 44.1).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, UUID

from app.db.base import Base, TimestampMixin

_TIMESTAMP = DateTime(timezone=True)


class LeadCampaign(Base, TimestampMixin):
    """A durable campaign container under ``/workspaces/{id}/campaigns``."""

    __tablename__ = "lead_campaigns"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "name",
            "direction",
            name="uq_lead_campaigns_workspace_name_direction",
        ),
        Index("ix_lead_campaigns_workspace_status", "workspace_id", "status"),
        Index("ix_lead_campaigns_workspace_source", "workspace_id", "source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(300), nullable=False)
    direction = Column(String(20), nullable=False)  # 'demand' | 'supply'
    status = Column(
        String(50), nullable=False, default="draft", server_default="draft"
    )
    # Payload gốc (CampaignSpec model_dump) — nullable vì campaign 'created'
    # qua CRUD (44.3) có thể chưa có spec.
    input_payload = Column(JSONB, nullable=True)
    # Denormalized schedule fields cho 44.2 (scheduler) — scalar nullable.
    schedule_frequency = Column(String(50), nullable=True)
    schedule_cron = Column(String(100), nullable=True)
    max_runs = Column(Integer, nullable=True)
    next_run_at = Column(_TIMESTAMP, nullable=True)
    # 'created' (CRUD) | 'execute' (implicit từ execute route) | 'api'
    source = Column(
        String(20), nullable=False, default="created", server_default="created"
    )
    skipped_by_quota = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_by = Column(UUID(as_uuid=True), nullable=True)


class CampaignRun(Base, TimestampMixin):
    """One execution of a lead campaign.

    Chỉ ``campaign_service.open_campaign_run`` được phép INSERT vào bảng này
    (seam duy nhất, có advisory lock + guard chạy đồng thời).
    """

    __tablename__ = "campaign_runs"

    __table_args__ = (
        Index(
            "ix_campaign_runs_workspace_campaign_created",
            "workspace_id",
            "campaign_id",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lead_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20), nullable=False, default="queued", server_default="queued"
    )
    trigger = Column(String(20), nullable=False)
    # spec.model_dump(mode="json") — python-mode crash trên UUID/datetime.
    spec_snapshot = Column(JSONB, nullable=True)
    started_at = Column(_TIMESTAMP, nullable=True)
    finished_at = Column(_TIMESTAMP, nullable=True)
    stats = Column(JSONB, nullable=True)
    cost_micros = Column(BIGINT, nullable=True)
    error = Column(String(2000), nullable=True)


class CampaignLead(Base, TimestampMixin):
    """Junction campaign↔lead; ``run_id`` ghi run đầu tiên attach lead.

    Composite FK ``(lead_id, workspace_id)`` — precedent
    ``app/models/leads/main.py`` LeadAssignment.
    """

    __tablename__ = "campaign_leads"

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_campaign_leads"),
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            ondelete="CASCADE",
            name="fk_campaign_leads_lead_id_workspace_id",
        ),
        UniqueConstraint(
            "campaign_id", "lead_id", name="uq_campaign_leads_campaign_lead"
        ),
        Index("ix_campaign_leads_campaign", "campaign_id"),
        Index("ix_campaign_leads_lead_workspace", "lead_id", "workspace_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lead_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    # 'buyer' (demand campaign) | 'supplier' (supply campaign)
    role = Column(String(20), nullable=False)
