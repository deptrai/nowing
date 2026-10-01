"""Pydantic schemas for Workspace SIP Trunks (Story 38.6 / BYO-SIP)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SipTrunkCreateRequest(BaseModel):
    """Payload to register a new SIP trunk for a workspace."""

    name: str = Field(..., min_length=1, max_length=100)
    brandname: str | None = Field(None, max_length=50)
    outbound_did: str = Field(..., min_length=5, max_length=30)
    sip_server: str = Field(..., min_length=3, max_length=255)
    sip_username: str = Field(..., min_length=1, max_length=100)
    sip_password: str = Field(..., min_length=1, max_length=255)
    livekit_trunk_id: str | None = Field(None, max_length=100)
    is_default: bool = False


class SipTrunkUpdateRequest(BaseModel):
    """Payload to update an existing SIP trunk."""

    name: str | None = Field(None, min_length=1, max_length=100)
    brandname: str | None = Field(None, max_length=50)
    outbound_did: str | None = Field(None, min_length=5, max_length=30)
    sip_server: str | None = Field(None, min_length=3, max_length=255)
    sip_username: str | None = Field(None, min_length=1, max_length=100)
    sip_password: str | None = Field(None, min_length=1, max_length=255)
    livekit_trunk_id: str | None = Field(None, max_length=100)
    is_default: bool | None = None
    status: str | None = Field(None, pattern="^(active|disabled)$")


class SipTrunkResponse(BaseModel):
    """Client-facing representation of a SIP trunk. Password is masked."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: int
    name: str
    brandname: str | None
    outbound_did: str
    sip_server: str
    sip_username: str
    # Password is ALWAYS masked in API responses to prevent leakage
    sip_password_masked: str = "********"
    livekit_trunk_id: str | None
    is_default: bool
    is_verified: bool
    status: str
    created_at: datetime
    updated_at: datetime


class SipTrunkResolved(BaseModel):
    """Internal representation with decrypted credentials for LiveKit dialing."""

    trunk_id: str
    workspace_id: int
    name: str
    brandname: str | None
    outbound_did: str
    sip_server: str
    sip_username: str
    sip_password: str  # Plaintext, decrypted for LiveKit SIP client only
    is_default: bool
    is_verified: bool
