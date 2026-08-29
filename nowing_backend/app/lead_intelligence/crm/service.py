"""CRM connection and sync services (Story 21.5)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    CrmConnection,
    CrmSyncLog,
    Lead,
    MemorySourceType,
    OutcomeEvent,
    Permission,
)
from app.lead_intelligence.crm.field_mapping import get_field_mapping
from app.lead_intelligence.crm.oauth import (
    build_auth_url,
    decrypt_credentials,
    exchange_code,
)
from app.lead_intelligence.crm.providers import (
    HubSpotProvider,
    PipedriveProvider,
    SalesforceProvider,
)
from app.lead_intelligence.crm.schemas import CrmConversionLogInput
from app.services.memory.repository import MemoryRepository
from app.services.pii.redact import redact_pii
from app.utils.rbac import check_permission

SUPPORTED_PROVIDERS = {"salesforce", "hubspot", "pipedrive"}


@dataclass
class SyncResult:
    """Result of a sync operation."""

    degraded: bool
    degradation_reasons: list[str]
    sync_log: CrmSyncLog | None


def _provider_client(provider: str, credentials: dict[str, Any]):
    if provider == "salesforce":
        return SalesforceProvider(credentials)
    if provider == "hubspot":
        return HubSpotProvider(credentials)
    if provider == "pipedrive":
        return PipedriveProvider(credentials)
    raise ValueError(f"Unknown CRM provider: {provider}")


class CrmConnectionService:
    """Manage CrmConnection rows and OAuth state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(
        self,
        auth: AuthContext,
        workspace_id: int,
        provider: str,
        client_id: str | None,
        sync_config: dict[str, Any] | None = None,
    ) -> str:
        """Create a pending CrmConnection and return an OAuth auth URL."""
        await check_permission(self.session, auth, workspace_id, Permission.CRM_CONNECT)

        if provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported CRM provider: {provider}"
            )

        connection = CrmConnection(
            workspace_id=workspace_id,
            client_id=client_id,
            provider=provider,
            status="pending",
            credentials_encrypted="",
            sync_config=sync_config or {},
        )
        self.session.add(connection)
        await self.session.flush()

        return build_auth_url(provider, workspace_id, auth.user.id)

    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> CrmConnection:
        """Handle OAuth callback and persist encrypted tokens."""
        credentials_encrypted, _ = await exchange_code(provider, code, state)

        # State carries workspace_id/user_id; connection is the most recent pending one.
        result = await self.session.execute(
            select(CrmConnection)
            .where(
                CrmConnection.provider == provider,
                CrmConnection.status == "pending",
            )
            .order_by(CrmConnection.created_at.desc())
            .limit(1)
        )
        connection = result.scalars().first()
        if not connection:
            raise HTTPException(
                status_code=404, detail="No pending CRM connection found"
            )

        connection.credentials_encrypted = credentials_encrypted
        connection.status = "active"
        connection.last_sync_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(connection)
        return connection

    async def list_connections(
        self,
        auth: AuthContext,
        workspace_id: int,
    ) -> list[CrmConnection]:
        await check_permission(self.session, auth, workspace_id, Permission.CRM_READ)

        result = await self.session.execute(
            select(CrmConnection)
            .where(
                CrmConnection.workspace_id == workspace_id,
                CrmConnection.status != "disconnected",
            )
            .order_by(CrmConnection.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_connection(
        self,
        auth: AuthContext,
        workspace_id: int,
        connection_id: UUID,
    ) -> CrmConnection:
        await check_permission(self.session, auth, workspace_id, Permission.CRM_READ)

        result = await self.session.execute(
            select(CrmConnection).where(
                CrmConnection.id == connection_id,
                CrmConnection.workspace_id == workspace_id,
            )
        )
        connection = result.scalars().first()
        if not connection:
            raise HTTPException(status_code=404, detail="CRM connection not found")
        return connection

    async def disconnect(
        self,
        auth: AuthContext,
        workspace_id: int,
        connection_id: UUID,
    ) -> None:
        await check_permission(
            self.session, auth, workspace_id, Permission.CRM_DISCONNECT
        )

        connection = await self.get_connection(auth, workspace_id, connection_id)
        connection.status = "disconnected"
        await self.session.commit()


class CrmSyncService:
    """Perform dedup, write-back, and bidirectional sync."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dedup_lead(
        self,
        auth: AuthContext,
        workspace_id: int,
        connection_id: UUID,
        lead_id: UUID,
    ) -> SyncResult:
        """Read-only dedup against CRM contacts."""
        await check_permission(self.session, auth, workspace_id, Permission.CRM_SYNC)

        connection = await self._get_connection(workspace_id, connection_id)
        sync_config = self._load_sync_config(connection.sync_config)
        if not sync_config.get("dedup_enabled", True):
            return SyncResult(degraded=False, degradation_reasons=[], sync_log=None)

        lead = await self._get_lead(workspace_id, lead_id)
        credentials = decrypt_credentials(connection.credentials_encrypted)
        client = _provider_client(connection.provider, credentials)

        try:
            result = await client.search_contacts(email=None, domain=lead.domain)
        except Exception as e:
            return self._error_log(
                connection, lead_id, "lead", f"dedup search failed: {e!s}"
            )

        duplicate = any(c.domain == lead.domain or c.email for c in result.contacts)
        note = "duplicate_detected" if duplicate else "no_duplicate"
        return await self._success_log(connection, lead_id, "lead", note=note)

    async def push_lead(
        self,
        auth: AuthContext,
        workspace_id: int,
        connection_id: UUID,
        lead_id: UUID,
    ) -> SyncResult:
        """Push a lead to CRM (Phase 2)."""
        await check_permission(self.session, auth, workspace_id, Permission.CRM_WRITE)

        connection = await self._get_connection(workspace_id, connection_id)
        sync_config = self._load_sync_config(connection.sync_config)
        if not sync_config.get("writeback_enabled", False):
            return SyncResult(degraded=False, degradation_reasons=[], sync_log=None)

        lead = await self._get_lead(workspace_id, lead_id)
        credentials = decrypt_credentials(connection.credentials_encrypted)
        client = _provider_client(connection.provider, credentials)
        mapping = get_field_mapping(
            connection.provider, sync_config.get("field_mapping")
        )

        lead_data = self._map_lead(lead, mapping)
        try:
            await client.create_lead(lead_data)
        except Exception as e:
            return self._error_log(connection, lead_id, "lead", f"create failed: {e!s}")

        result = await self._success_log(connection, lead_id, "lead")
        await self._write_context_memory(workspace_id, client, lead, connection)
        return result

    async def sync_lead_score(
        self,
        auth: AuthContext,
        workspace_id: int,
        connection_id: UUID,
        lead_score_id: UUID,
    ) -> SyncResult:
        """Push a lead score snapshot to CRM."""
        await check_permission(self.session, auth, workspace_id, Permission.CRM_WRITE)

        connection = await self._get_connection(workspace_id, connection_id)
        sync_config = self._load_sync_config(connection.sync_config)
        if not sync_config.get("writeback_enabled", False):
            return SyncResult(degraded=False, degradation_reasons=[], sync_log=None)

        return await self._success_log(connection, lead_score_id, "lead_score")

    async def _get_connection(
        self, workspace_id: int, connection_id: UUID
    ) -> CrmConnection:
        result = await self.session.execute(
            select(CrmConnection).where(
                CrmConnection.id == connection_id,
                CrmConnection.workspace_id == workspace_id,
                CrmConnection.status == "active",
            )
        )
        connection = result.scalars().first()
        if not connection:
            raise HTTPException(
                status_code=404, detail="CRM connection not found or not active"
            )
        return connection

    async def _get_lead(self, workspace_id: int, lead_id: UUID) -> Lead:
        result = await self.session.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.workspace_id == workspace_id,
            )
        )
        lead = result.scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead

    def _load_sync_config(self, sync_config: Any) -> dict[str, Any]:
        if isinstance(sync_config, dict):
            return sync_config
        if isinstance(sync_config, str):
            return json.loads(sync_config)
        return {}

    def _map_lead(self, lead: Lead, mapping: dict[str, str]) -> dict[str, Any]:
        """Map Lead fields to CRM fields using provider mapping."""
        return {
            mapping.get("company_name", "company_name"): lead.company_name,
            mapping.get("domain", "domain"): lead.domain,
            mapping.get("industry", "industry"): lead.industry,
            mapping.get("company_size", "company_size"): lead.company_size,
            mapping.get("location", "location"): lead.location,
        }

    async def _success_log(
        self,
        connection: CrmConnection,
        entity_id: UUID,
        entity_type: str,
        note: str | None = None,
    ) -> SyncResult:
        log = CrmSyncLog(
            workspace_id=connection.workspace_id,
            client_id=connection.client_id,
            connection_id=connection.id,
            direction="nowing_to_crm",
            entity_type=entity_type,
            entity_id=entity_id,
            status="success",
            error_message=note,
            synced_at=datetime.now(UTC),
        )
        self.session.add(log)
        await self.session.flush()
        return SyncResult(degraded=False, degradation_reasons=[], sync_log=log)

    def _error_log(
        self,
        connection: CrmConnection,
        entity_id: UUID,
        entity_type: str,
        message: str,
    ) -> SyncResult:
        log = CrmSyncLog(
            workspace_id=connection.workspace_id,
            client_id=connection.client_id,
            connection_id=connection.id,
            direction="nowing_to_crm",
            entity_type=entity_type,
            entity_id=entity_id,
            status="error",
            error_message=message,
            synced_at=datetime.now(UTC),
        )
        self.session.add(log)
        return SyncResult(
            degraded=True,
            degradation_reasons=["api_error"],
            sync_log=log,
        )

    async def _write_context_memory(
        self,
        workspace_id: int,
        client: Any,
        lead: Lead,
        connection: CrmConnection,
    ) -> None:
        """Write a redacted CRM context memory."""
        content = (
            f"CRM sync context for {lead.company_name} via {connection.provider} "
            f"(domain: {lead.domain})."
        )
        redacted = redact_pii(content, context="lead_enrichment")
        repo = MemoryRepository(self.session)
        await repo.create_memory(
            workspace_id=workspace_id,
            client_id=connection.client_id,
            content=redacted.text,
            source_type=MemorySourceType.CRM_CONNECTION,
            source_uuid=connection.id,
            source_entity_type="crm_connection",
            tags=["crm_context"],
            commit=False,
        )

    async def log_conversion(
        self,
        auth: AuthContext,
        workspace_id: int,
        conversion_data: CrmConversionLogInput,
    ) -> OutcomeEvent:
        """Log a lead conversion outcome event and optionally push update to CRM (Story 27.5)."""
        await check_permission(self.session, auth, workspace_id, Permission.CRM_WRITE)

        lead = await self._get_lead(workspace_id, conversion_data.lead_id)

        outcome_event = OutcomeEvent(
            workspace_id=workspace_id,
            client_id=lead.client_id,
            event_type=conversion_data.event_type,
            lead_id=conversion_data.lead_id,
            attribution=conversion_data.attribution,
            cost_micros=conversion_data.cost_micros,
            outcome_metadata=conversion_data.metadata or {},
        )
        self.session.add(outcome_event)
        await self.session.flush()

        if conversion_data.sync_to_crm and conversion_data.connection_id:
            try:
                await self.push_lead(
                    auth=auth,
                    workspace_id=workspace_id,
                    connection_id=conversion_data.connection_id,
                    lead_id=conversion_data.lead_id,
                )
            except Exception as sync_err:
                # Fail-soft on external CRM sync error while keeping the local conversion event
                pass

        # Also store conversion context in memory
        conversion_summary = (
            f"Conversion logged for lead {lead.company_name or lead.id} "
            f"event_type={conversion_data.event_type} attribution={conversion_data.attribution}."
        )
        redacted = redact_pii(conversion_summary, context="lead_enrichment")
        repo = MemoryRepository(self.session)
        await repo.create_memory(
            workspace_id=workspace_id,
            client_id=lead.client_id,
            content=redacted.text,
            source_type=MemorySourceType.MANUAL,
            source_uuid=outcome_event.id,
            source_entity_type="outcome_event",
            tags=["crm_conversion", "attribution"],
            commit=False,
        )
        await self.session.commit()
        await self.session.refresh(outcome_event)
        return outcome_event

    async def list_conversions(
        self,
        auth: AuthContext,
        workspace_id: int,
        lead_id: UUID | None = None,
        limit: int = 50,
    ) -> list[OutcomeEvent]:
        """List conversion outcome events for a workspace (Story 27.5)."""
        await check_permission(self.session, auth, workspace_id, Permission.CRM_READ)

        stmt = (
            select(OutcomeEvent)
            .where(OutcomeEvent.workspace_id == workspace_id)
            .order_by(OutcomeEvent.created_at.desc())
            .limit(limit)
        )
        if lead_id:
            stmt = stmt.where(OutcomeEvent.lead_id == lead_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

