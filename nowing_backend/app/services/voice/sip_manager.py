"""Workspace SIP Trunk & Voice Brandname Management (Story 38.6 / BYO-SIP).

Manages multi-tenant SIP trunk credentials:
- AES-256-GCM encryption of SIP passwords via TokenEncryption (PII Vault).
- Workspace data isolation (no cross-tenant leakage).
- Password masking in public responses.
- Dynamic trunk resolution with system default fallback.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import WorkspaceSipTrunk
from app.schemas.voice_sip import (
    SipTrunkCreateRequest,
    SipTrunkResolved,
    SipTrunkUpdateRequest,
)
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


class SipCredentialDecryptionError(Exception):
    """Raised when stored encrypted SIP credentials cannot be decrypted."""


class SipTrunkManager:
    """Manages workspace SIP trunks with encrypted credential storage."""

    def __init__(self, *, secret_key: str | None = None) -> None:
        key = (
            secret_key
            or getattr(config, "SECRET_KEY", None)
            or "default_telephony_secret"
        )
        self._crypto = TokenEncryption(key)

    def encrypt_password(self, plaintext: str) -> str:
        """Encrypt SIP password using AES-256-GCM."""
        return self._crypto.encrypt_token(plaintext)

    def decrypt_password(self, ciphertext: str) -> str:
        """Decrypt stored SIP password. Raises SipCredentialDecryptionError on failure."""
        try:
            return self._crypto.decrypt_token(ciphertext)
        except Exception as exc:
            raise SipCredentialDecryptionError(
                f"Failed to decrypt SIP trunk credentials: {exc}"
            ) from exc

    async def create_trunk(
        self,
        session: AsyncSession,
        workspace_id: int,
        req: SipTrunkCreateRequest,
    ) -> WorkspaceSipTrunk:
        """Create a new SIP trunk for *workspace_id* with encrypted credentials."""
        # If this is marked default, unset existing defaults first
        if req.is_default:
            await session.execute(
                update(WorkspaceSipTrunk)
                .where(WorkspaceSipTrunk.workspace_id == workspace_id)
                .values(is_default=False)
            )

        encrypted_pwd = self.encrypt_password(req.sip_password)

        trunk = WorkspaceSipTrunk(
            workspace_id=workspace_id,
            name=req.name,
            brandname=req.brandname,
            outbound_did=req.outbound_did,
            sip_server=req.sip_server,
            sip_username=req.sip_username,
            sip_password_encrypted=encrypted_pwd,
            livekit_trunk_id=req.livekit_trunk_id,
            is_default=req.is_default,
            is_verified=False,  # Brandnames require operator/telco verification
            status="active",
        )
        session.add(trunk)
        await session.flush()
        logger.info(
            "[SipTrunk] Created trunk id=%s ws=%s did=%s default=%s",
            trunk.id,
            workspace_id,
            trunk.outbound_did,
            trunk.is_default,
        )
        return trunk

    async def list_trunks(
        self,
        session: AsyncSession,
        workspace_id: int,
    ) -> list[WorkspaceSipTrunk]:
        """List all SIP trunks for a workspace."""
        stmt = (
            select(WorkspaceSipTrunk)
            .where(WorkspaceSipTrunk.workspace_id == workspace_id)
            .order_by(WorkspaceSipTrunk.is_default.desc(), WorkspaceSipTrunk.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_trunk(
        self,
        session: AsyncSession,
        workspace_id: int,
        trunk_id: UUID,
    ) -> WorkspaceSipTrunk | None:
        """Fetch a specific trunk belonging to *workspace_id*."""
        stmt = select(WorkspaceSipTrunk).where(
            WorkspaceSipTrunk.id == trunk_id,
            WorkspaceSipTrunk.workspace_id == workspace_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_trunk(
        self,
        session: AsyncSession,
        workspace_id: int,
        trunk_id: UUID,
        req: SipTrunkUpdateRequest,
    ) -> WorkspaceSipTrunk | None:
        """Update an existing SIP trunk."""
        trunk = await self.get_trunk(session, workspace_id, trunk_id)
        if not trunk:
            return None

        if req.is_default is True:
            await session.execute(
                update(WorkspaceSipTrunk)
                .where(WorkspaceSipTrunk.workspace_id == workspace_id)
                .values(is_default=False)
            )
            trunk.is_default = True
        elif req.is_default is False:
            trunk.is_default = False

        if req.name is not None:
            trunk.name = req.name
        if req.brandname is not None:
            trunk.brandname = req.brandname
        if req.outbound_did is not None:
            trunk.outbound_did = req.outbound_did
        if req.sip_server is not None:
            trunk.sip_server = req.sip_server
        if req.sip_username is not None:
            trunk.sip_username = req.sip_username
        if req.sip_password is not None:
            trunk.sip_password_encrypted = self.encrypt_password(req.sip_password)
        if req.livekit_trunk_id is not None:
            trunk.livekit_trunk_id = req.livekit_trunk_id
        if req.status is not None:
            trunk.status = req.status

        await session.flush()
        return trunk

    async def delete_trunk(
        self,
        session: AsyncSession,
        workspace_id: int,
        trunk_id: UUID,
    ) -> bool:
        """Delete a SIP trunk from a workspace."""
        trunk = await self.get_trunk(session, workspace_id, trunk_id)
        if not trunk:
            return False
        await session.delete(trunk)
        await session.flush()
        logger.info("[SipTrunk] Deleted trunk id=%s ws=%s", trunk_id, workspace_id)
        return True

    async def set_default_trunk(
        self,
        session: AsyncSession,
        workspace_id: int,
        trunk_id: UUID,
    ) -> WorkspaceSipTrunk | None:
        """Atomically promote a trunk to be the default for the workspace."""
        trunk = await self.get_trunk(session, workspace_id, trunk_id)
        if not trunk:
            return None

        # Reset all trunks in workspace
        await session.execute(
            update(WorkspaceSipTrunk)
            .where(WorkspaceSipTrunk.workspace_id == workspace_id)
            .values(is_default=False)
        )
        trunk.is_default = True
        await session.flush()
        logger.info("[SipTrunk] Set default trunk id=%s ws=%s", trunk_id, workspace_id)
        return trunk

    async def resolve_workspace_trunk(
        self,
        session: AsyncSession,
        workspace_id: int,
    ) -> SipTrunkResolved:
        """Resolve the active SIP trunk for a call, falling back to system default.

        Resolution Cascade:
        1. Default active trunk configured for the workspace.
        2. First active trunk configured for the workspace.
        3. System default fallback using ``config.SIP_DEFAULT_TRUNK_ID``.
        """
        stmt = (
            select(WorkspaceSipTrunk)
            .where(
                WorkspaceSipTrunk.workspace_id == workspace_id,
                WorkspaceSipTrunk.status == "active",
            )
            .order_by(
                WorkspaceSipTrunk.is_default.desc(),
                WorkspaceSipTrunk.created_at.asc(),
            )
        )
        res = await session.execute(stmt)
        trunk = res.scalars().first()

        if trunk:
            try:
                plaintext_password = self.decrypt_password(
                    trunk.sip_password_encrypted
                )
                return SipTrunkResolved(
                    trunk_id=trunk.livekit_trunk_id or str(trunk.id),
                    workspace_id=workspace_id,
                    name=trunk.name,
                    brandname=trunk.brandname,
                    outbound_did=trunk.outbound_did,
                    sip_server=trunk.sip_server,
                    sip_username=trunk.sip_username,
                    sip_password=plaintext_password,
                    is_default=trunk.is_default,
                    is_verified=trunk.is_verified,
                )
            except SipCredentialDecryptionError as exc:
                logger.error(
                    "[SipTrunk] Decryption failed for ws=%s trunk=%s — falling back: %s",
                    workspace_id,
                    trunk.id,
                    exc,
                )

        # Fallback to system-level defaults
        default_trunk_id = getattr(config, "SIP_DEFAULT_TRUNK_ID", "default_trunk")
        default_server = getattr(config, "SIP_OUTBOUND_GATEWAY_HOST", "127.0.0.1")
        default_port = getattr(config, "SIP_OUTBOUND_GATEWAY_PORT", 5060)

        logger.info(
            "[SipTrunk] Using system fallback trunk %s for ws=%s",
            default_trunk_id,
            workspace_id,
        )
        return SipTrunkResolved(
            trunk_id=default_trunk_id,
            workspace_id=workspace_id,
            name="System Default Trunk",
            brandname=None,
            outbound_did="+842871000000",
            sip_server=f"{default_server}:{default_port}",
            sip_username="system_nowing",
            sip_password="",
            is_default=True,
            is_verified=False,
        )
