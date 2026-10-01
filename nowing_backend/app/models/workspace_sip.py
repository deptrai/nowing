"""Workspace SIP Trunk & Voice Brandname model (Story 38.6 / BYO-SIP)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.models.workspaces import TimestampMixin


class WorkspaceSipTrunk(Base, TimestampMixin):
    """Multi-tenant SIP Trunk configuration per workspace.

    Supports Voice Brandname, BYO-SIP credentials (AES-256-GCM encrypted),
    and dynamic DID allocation.
    """

    __tablename__ = "workspace_sip_trunks"
    __table_args__ = (
        Index("ix_workspace_sip_trunks_ws_active", "workspace_id", "status"),
        Index("ix_workspace_sip_trunks_ws_default", "workspace_id", "is_default"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    brandname = Column(String(50), nullable=True)  # Voice Brandname (e.g. "NOWING")
    outbound_did = Column(String(30), nullable=False)  # E.164 phone (e.g. "+842871099999")
    sip_server = Column(String(255), nullable=False)  # host:port
    sip_username = Column(String(100), nullable=False)
    sip_password_encrypted = Column(String(512), nullable=False)  # AES-256-GCM cipher
    livekit_trunk_id = Column(String(100), nullable=True)  # LiveKit SIP Gateway trunk ID
    is_default = Column(Boolean, nullable=False, default=False)
    is_verified = Column(Boolean, nullable=False, default=False)  # Voice Brandname verified
    status = Column(String(20), nullable=False, default="active")  # 'active', 'disabled'
