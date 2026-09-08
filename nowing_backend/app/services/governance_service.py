"""Service for workspace governance console (Story 29.6 / FR-97).

Composes existing services rather than reimplementing:
- MemoryErasureService for single right-to-delete
- BulkOpsService + BulkOpJob for bulk right-to-delete (AC-4)
- create_dnc_record_service + DncComplianceService for DNC
- Workspace retention fields already on the model
- AuditEvent for governance audit log
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    AuditEvent,
    GlobalDncRecord,
    Memory,
    MemorySourceLegalTier,
    User,
    Workspace,
    WorkspaceDncRecord,
)
from app.models.bulk_ops import BulkAction
from app.schemas.bulk_ops import FilterClause
from app.schemas.dnc import DncRecordCreate as ExistingDncRecordCreate
from app.schemas.governance import (
    AuditLogFilter,
    AuditLogRead,
    DncRecordCreate,
    DncRecordRead,
    GovernanceOverviewRead,
    RetentionPolicyRead,
    RetentionPolicyUpdate,
    RightToDeleteRequest,
    RightToDeleteResponse,
    SourceRiskTierRead,
    SourceRiskTierUpdate,
    WorkspaceStatusRead,
)
from app.services.bulk_ops_service import BulkOpsService
from app.services.memory.erasure_service import MemoryErasureService

logger = logging.getLogger(__name__)


class GovernanceService:
    """Business logic for the governance console."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bulk_ops = BulkOpsService()

    # ------------------------------------------------------------------
    # Overview & retention policy
    # ------------------------------------------------------------------

    async def get_overview(
        self, workspace_id: int
    ) -> GovernanceOverviewRead:
        """Return the combined governance console payload."""
        workspace = await self._get_workspace_or_404(workspace_id)

        retention = RetentionPolicyRead(
            document_retention_days=workspace.document_retention_days,
            auto_archive_enabled=workspace.auto_archive_enabled,
            document_retention_action=workspace.document_retention_action,
            memory_retention_days=workspace.memory_retention_days,
            memory_auto_archive_enabled=workspace.memory_auto_archive_enabled,
            memory_retention_action=workspace.memory_retention_action,
        )

        source_tiers = await self.list_source_risk_tiers()
        dnc_records = await self.list_dnc_records(workspace_id)

        workspace_status = WorkspaceStatusRead(
            archived_at=workspace.archived_at,
            can_restore=workspace.archived_at is not None,
            scrape_paused_at=workspace.scrape_paused_at,
        )

        deployment_mode = getattr(config, "DEPLOYMENT_MODE", "cloud")

        return GovernanceOverviewRead(
            retention_policy=retention,
            source_risk_tiers=source_tiers,
            dnc_records=dnc_records,
            workspace_status=workspace_status,
            deployment_mode=deployment_mode,
        )

    async def update_retention_policy(
        self,
        workspace_id: int,
        payload: RetentionPolicyUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> RetentionPolicyRead:
        """Update workspace retention policy with source-risk-tier validation."""
        workspace = await self._get_workspace_or_404(workspace_id)

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return RetentionPolicyRead(
                document_retention_days=workspace.document_retention_days,
                auto_archive_enabled=workspace.auto_archive_enabled,
                document_retention_action=workspace.document_retention_action,
                memory_retention_days=workspace.memory_retention_days,
                memory_auto_archive_enabled=workspace.memory_auto_archive_enabled,
                memory_retention_action=workspace.memory_retention_action,
            )

        # Serialize concurrent retention updates
        await self.session.execute(text("SET LOCAL lock_timeout = '10s'"))
        locked = await self.session.execute(
            select(Workspace).filter(Workspace.id == workspace_id).with_for_update()
        )
        locked_ws = locked.scalars().first()
        if not locked_ws:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Compute final state
        new_doc_days = update_data.get(
            "document_retention_days", locked_ws.document_retention_days
        )
        new_doc_enabled = update_data.get(
            "auto_archive_enabled", locked_ws.auto_archive_enabled
        )
        new_doc_action = update_data.get(
            "document_retention_action", locked_ws.document_retention_action
        )
        new_mem_days = update_data.get(
            "memory_retention_days", locked_ws.memory_retention_days
        )
        new_mem_enabled = update_data.get(
            "memory_auto_archive_enabled", locked_ws.memory_auto_archive_enabled
        )
        new_mem_action = update_data.get(
            "memory_retention_action", locked_ws.memory_retention_action
        )

        # Reject explicit nulls
        if "auto_archive_enabled" in update_data and new_doc_enabled is None:
            raise HTTPException(status_code=400, detail="auto_archive_enabled cannot be null")
        if "document_retention_action" in update_data and new_doc_action is None:
            raise HTTPException(
                status_code=400, detail="document_retention_action cannot be null"
            )
        if "memory_auto_archive_enabled" in update_data and new_mem_enabled is None:
            raise HTTPException(
                status_code=400, detail="memory_auto_archive_enabled cannot be null"
            )
        if "memory_retention_action" in update_data and new_mem_action is None:
            raise HTTPException(
                status_code=400, detail="memory_retention_action cannot be null"
            )

        # Invariants
        if new_doc_enabled:
            if new_doc_days is None or new_doc_days <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="document_retention_days must be positive when auto_archive_enabled is true",
                )
            if new_doc_days > 36500:
                raise HTTPException(
                    status_code=400,
                    detail="document_retention_days must not exceed 36500",
                )
            if not new_doc_action:
                raise HTTPException(
                    status_code=400,
                    detail="document_retention_action is required when auto_archive_enabled is true",
                )

        if new_mem_enabled:
            if new_mem_days is None or new_mem_days <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="memory_retention_days must be positive when memory_auto_archive_enabled is true",
                )
            if new_mem_days > 36500:
                raise HTTPException(
                    status_code=400,
                    detail="memory_retention_days must not exceed 36500",
                )
            if not new_mem_action:
                raise HTTPException(
                    status_code=400,
                    detail="memory_retention_action is required when memory_auto_archive_enabled is true",
                )

        # AC-2/AC-3: do not allow memory retention below the recommended
        # minimum for any high-risk source type.
        if new_mem_enabled and new_mem_days is not None:
            high_risk_sources = await self._list_high_risk_sources()
            if high_risk_sources:
                recommended = [
                    t.recommended_retention_days
                    for t in high_risk_sources
                    if t.recommended_retention_days is not None
                ]
                if recommended:
                    min_recommended = min(recommended)
                    if new_mem_days < min_recommended:
                        names = [t.source_type for t in high_risk_sources]
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"memory_retention_days={new_mem_days} is below the "
                                f"recommended minimum of {min_recommended} days for "
                                f"high-risk sources: {names}"
                            ),
                        )

        # Apply
        for key, value in update_data.items():
            setattr(locked_ws, key, value)

        # Audit
        await self._write_audit(
            action="governance.retention_policy.update",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={"workspace_id": workspace_id, **update_data},
        )

        await self.session.commit()
        await self.session.refresh(locked_ws)

        return RetentionPolicyRead(
            document_retention_days=locked_ws.document_retention_days,
            auto_archive_enabled=locked_ws.auto_archive_enabled,
            document_retention_action=locked_ws.document_retention_action,
            memory_retention_days=locked_ws.memory_retention_days,
            memory_auto_archive_enabled=locked_ws.memory_auto_archive_enabled,
            memory_retention_action=locked_ws.memory_retention_action,
        )

    # ------------------------------------------------------------------
    # Source risk tiers
    # ------------------------------------------------------------------

    async def list_source_risk_tiers(self) -> list[SourceRiskTierRead]:
        """Return all configured source risk tiers."""
        stmt = select(MemorySourceLegalTier).order_by(MemorySourceLegalTier.source_type)
        result = await self.session.execute(stmt)
        return [SourceRiskTierRead.model_validate(r) for r in result.scalars().all()]

    async def upsert_source_risk_tier(
        self,
        workspace_id: int,
        payload: SourceRiskTierUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> SourceRiskTierRead:
        """Create or update a source risk tier; pause scraping on high risk."""
        source_type = payload.source_type.value
        stmt = select(MemorySourceLegalTier).where(
            MemorySourceLegalTier.source_type == source_type
        )
        result = await self.session.execute(stmt)
        tier = result.scalars().first()
        previous_risk_tier = tier.risk_tier if tier else None

        if tier:
            tier.risk_tier = payload.risk_tier
            tier.recommended_retention_days = payload.recommended_retention_days
            tier.notes = payload.notes
        else:
            tier = MemorySourceLegalTier(
                source_type=source_type,
                risk_tier=payload.risk_tier,
                recommended_retention_days=payload.recommended_retention_days,
                notes=payload.notes,
            )
            self.session.add(tier)

        await self.session.flush()

        # AC-3/3: pause scraping for this workspace when source reclassified to high risk.
        if payload.risk_tier == "high":
            await self._pause_scraping_for_source(
                workspace_id, source_type, actor_id=actor_id
            )
        # AC-3/5: resuming from high → lower risk re-enables scraping for this
        # workspace and writes `governance.source_risk_tier_resume` audit.
        elif previous_risk_tier == "high" and payload.risk_tier in {"low", "medium"}:
            await self._resume_scraping_for_source(
                workspace_id, source_type, actor_id=actor_id
            )

        await self._write_audit(
            action="governance.source_risk_tier.upsert",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={"workspace_id": None, **payload.model_dump()},
        )

        await self.session.commit()
        await self.session.refresh(tier)
        return SourceRiskTierRead.model_validate(tier)

    async def _list_high_risk_sources(self) -> list[MemorySourceLegalTier]:
        stmt = select(MemorySourceLegalTier).where(
            MemorySourceLegalTier.risk_tier == "high"
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _pause_scraping_for_source(
        self,
        workspace_id: int,
        source_type: str,
        *,
        actor_id: UUID | None = None,
    ) -> None:
        """Soft-pause scraping for a high-risk source in the current workspace.

        AC-3/3: pause is workspace-scoped (single workspace only), not global.
        """
        now = datetime.now(UTC)
        stmt = select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.archived_at.is_(None),
            Workspace.scrape_paused_at.is_(None),
        )
        result = await self.session.execute(stmt)
        ws = result.scalars().first()

        if not ws:
            logger.debug(
                "governance.scrape_paused skipped",
                extra={
                    "workspace_id": workspace_id,
                    "source_type": source_type,
                    "reason": "already_paused_or_archived",
                },
            )
            return

        ws.scrape_paused_at = now
        ws.api_access_enabled = False

        logger.info(
            "governance.scrape_paused",
            extra={
                "workspace_id": workspace_id,
                "source_type": source_type,
                "actor_id": str(actor_id) if actor_id else None,
            },
        )
        await self._write_audit(
            action="governance.scrape_paused",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={
                "workspace_id": workspace_id,
                "source_type": source_type,
                "scrape_paused_at": now.isoformat(),
            },
        )

    async def _resume_scraping_for_source(
        self,
        workspace_id: int,
        source_type: str,
        *,
        actor_id: UUID | None = None,
    ) -> None:
        """Resume scraping for this workspace when a source is downgraded.

        AC-3/5: resumption writes `governance.source_risk_tier_resume` audit.
        """
        stmt = select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.archived_at.is_(None),
            Workspace.scrape_paused_at.isnot(None),
        )
        result = await self.session.execute(stmt)
        ws = result.scalars().first()

        if not ws:
            logger.debug(
                "governance.scrape_resumed skipped",
                extra={
                    "workspace_id": workspace_id,
                    "source_type": source_type,
                    "reason": "not_paused_or_archived",
                },
            )
            return

        ws.scrape_paused_at = None
        ws.api_access_enabled = True

        logger.info(
            "governance.scrape_resumed",
            extra={
                "workspace_id": workspace_id,
                "source_type": source_type,
                "actor_id": str(actor_id) if actor_id else None,
            },
        )
        await self._write_audit(
            action="governance.source_risk_tier.resume",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={
                "workspace_id": workspace_id,
                "source_type": source_type,
                "scrape_paused_at": None,
            },
        )

    # ------------------------------------------------------------------
    # DNC records
    # ------------------------------------------------------------------

    async def list_dnc_records(self, workspace_id: int) -> list[DncRecordRead]:
        """List workspace DNC records, flagging those superseded by global DNC."""
        stmt = select(WorkspaceDncRecord).where(
            WorkspaceDncRecord.workspace_id == workspace_id
        )
        result = await self.session.execute(stmt)
        records = result.scalars().all()

        global_stmt = select(GlobalDncRecord.value_hmac)
        global_result = await self.session.execute(global_stmt)
        global_hmacs = {row[0] for row in global_result.all()}

        out: list[DncRecordRead] = []
        for r in records:
            out.append(
                DncRecordRead(
                    id=str(r.id),
                    record_type=r.record_type,
                    value=r.value,
                    value_hmac=r.value_hmac,
                    reason=r.reason,
                    source=r.source,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    superseded_by_global=r.value_hmac in global_hmacs,
                )
            )
        return out

    async def create_dnc_record(
        self,
        workspace_id: int,
        payload: DncRecordCreate,
        *,
        actor_id: UUID | None = None,
    ) -> DncRecordRead:
        """Create a workspace DNC record via the existing service."""
        from app.routes.dnc_routes import create_dnc_record_service

        record = await create_dnc_record_service(
            self.session,
            workspace_id,
            ExistingDncRecordCreate(
                record_type=payload.record_type,
                value=payload.value,
                reason=payload.reason or "Opt-out requested",
            ),
            source="governance_console",
        )

        await self._write_audit(
            action="governance.dnc_record.create",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={
                "workspace_id": workspace_id,
                "record_id": str(record["id"]),
                **payload.model_dump(),
            },
        )
        await self.session.commit()

        # Check whether the new record is superseded by a global DNC entry.
        superseded = False
        try:
            global_stmt = select(GlobalDncRecord).where(
                GlobalDncRecord.record_type == record["record_type"],
                GlobalDncRecord.value_hmac == record["value_hmac"],
            )
            global_res = await self.session.execute(global_stmt)
            superseded = global_res.scalars().first() is not None
        except Exception:
            logger.warning(
                "governance.dnc_record.create global check failed",
                extra={
                    "record_type": record["record_type"],
                    "value_hmac": record["value_hmac"],
                },
            )

        return DncRecordRead(
            id=record["id"],
            record_type=record["record_type"],
            value=record["value"],
            value_hmac=record["value_hmac"],
            reason=record["reason"],
            source=record["source"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            superseded_by_global=superseded,
        )

    async def delete_dnc_record(
        self,
        workspace_id: int,
        record_id: str,
        *,
        actor_id: UUID | None = None,
    ) -> None:
        """Delete a workspace DNC record."""
        stmt = select(WorkspaceDncRecord).where(
            and_(
                WorkspaceDncRecord.id == record_id,
                WorkspaceDncRecord.workspace_id == workspace_id,
            )
        )
        result = await self.session.execute(stmt)
        record = result.scalars().first()
        if not record:
            raise HTTPException(status_code=404, detail="DNC record not found")

        await self._write_audit(
            action="governance.dnc_record.delete",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={
                "workspace_id": workspace_id,
                "record_id": str(record_id),
                "record_type": record.record_type,
                "value_hmac": record.value_hmac,
            },
        )
        await self.session.delete(record)
        await self.session.commit()

        from app.lead_intelligence.dnc.service import DncComplianceService

        await DncComplianceService().invalidate_workspace_cache(workspace_id)

    # ------------------------------------------------------------------
    # Right-to-delete
    # ------------------------------------------------------------------

    async def right_to_delete(
        self,
        workspace_id: int,
        payload: RightToDeleteRequest,
        *,
        actor_id: UUID | None = None,
    ) -> RightToDeleteResponse:
        """Handle single or bulk right-to-delete per AC-4."""
        if payload.type == "single_memory":
            if payload.memory_id is None:
                raise HTTPException(
                    status_code=422, detail="memory_id is required for single_memory"
                )
            return await self._delete_single_memory(
                workspace_id, payload, actor_id=actor_id
            )
        return await self._delete_bulk(workspace_id, payload, actor_id=actor_id)

    async def _delete_single_memory(
        self,
        workspace_id: int,
        payload: RightToDeleteRequest,
        *,
        actor_id: UUID | None,
    ) -> RightToDeleteResponse:
        """Single memory delete via MemoryErasureService."""
        svc = MemoryErasureService(self.session)
        memory = await self.session.get(Memory, payload.memory_id)
        if not memory or memory.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Memory not found")

        if payload.dry_run:
            return RightToDeleteResponse(
                dry_run=True, affected_count=1, preview_memory_ids=[payload.memory_id]
            )

        actor = await self.session.get(User, actor_id) if actor_id else None
        deleted = await svc.delete_memory(
            workspace_id=workspace_id,
            memory_id=payload.memory_id,
            actor=actor,
            reason=payload.reason,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")
        return RightToDeleteResponse(
            dry_run=False, affected_count=1, preview_memory_ids=[payload.memory_id]
        )

    async def _delete_bulk(
        self,
        workspace_id: int,
        payload: RightToDeleteRequest,
        *,
        actor_id: UUID | None,
    ) -> RightToDeleteResponse:
        """Bulk right-to-delete via BulkOpsService (AC-4)."""
        filters: list[FilterClause] = [
            FilterClause(field="workspace_id", operator="eq", value=workspace_id),
        ]
        if payload.source_type:
            filters.append(
                FilterClause(field="source_type", operator="eq", value=payload.source_type.value)
            )
        if payload.source_id:
            filters.append(
                FilterClause(field="source_id", operator="eq", value=payload.source_id)
            )
        if payload.created_before:
            filters.append(
                FilterClause(
                    field="created_before",
                    operator="lt",
                    value=payload.created_before.isoformat(),
                )
            )
        if payload.created_after:
            filters.append(
                FilterClause(
                    field="created_after",
                    operator="gt",
                    value=payload.created_after.isoformat(),
                )
            )

        if payload.source_entity_type:
            filters.append(
                FilterClause(
                    field="source_entity_type",
                    operator="eq",
                    value=payload.source_entity_type,
                )
            )

        action_params: dict[str, Any] = {"reason": payload.reason}

        if payload.dry_run:
            dry = await self.bulk_ops.dry_run(
                self.session,
                BulkAction.DELETE_SOURCE_TYPE_MEMORIES,
                filters,
                action_params,
                workspace_id=workspace_id,
            )
            return RightToDeleteResponse(
                dry_run=True,
                affected_count=dry.total_count,
                preview_memory_ids=[s["id"] for s in dry.sample_subjects],
            )

        actor = await self.session.get(User, actor_id) if actor_id else None
        if not actor:
            raise HTTPException(status_code=401, detail="Actor required")

        exec_result = await self.bulk_ops.execute(
            self.session,
            BulkAction.DELETE_SOURCE_TYPE_MEMORIES,
            filters,
            action_params,
            actor,
            workspace_id=workspace_id,
            idempotency_key=f"rtd-{workspace_id}-{actor_id}-{_uuid.uuid4().hex[:16]}",
        )

        # Re-fetch the job for the total count
        job = await self.bulk_ops.get_job(
            self.session, exec_result.job_id, actor, workspace_id=workspace_id
        )
        return RightToDeleteResponse(
            dry_run=False,
            affected_count=job.total_count or 0,
            job_id=str(exec_result.job_id),
            status=str(exec_result.status),
        )

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    async def list_audit_log(
        self,
        workspace_id: int,
        filters: AuditLogFilter,
    ) -> list[AuditLogRead]:
        """Query governance audit events for the workspace.

        `AuditEvent` has no dedicated workspace_id column; the workspace scope is
        stored in `subject_id` (governance mutations) or inside `diff_payload` for
        bulk-op and memory-delete events.
        """
        conditions = [
            AuditEvent.diff_payload["workspace_id"].astext == str(workspace_id)
        ]
        if filters.action_prefix:
            conditions.append(AuditEvent.action.like(f"{filters.action_prefix}%"))
        if filters.created_after:
            conditions.append(AuditEvent.created_at >= filters.created_after)
        if filters.created_before:
            conditions.append(AuditEvent.created_at <= filters.created_before)

        stmt = (
            select(AuditEvent)
            .where(*conditions)
            .order_by(AuditEvent.created_at.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        result = await self.session.execute(stmt)
        return [AuditLogRead.model_validate(r) for r in result.scalars().all()]

    # ------------------------------------------------------------------
    # Workspace lifecycle
    # ------------------------------------------------------------------

    async def archive_workspace(
        self, workspace_id: int, *, actor_id: UUID | None = None
    ) -> WorkspaceStatusRead:
        """Archive a workspace (soft-delete lifecycle)."""
        workspace = await self._get_workspace_or_404(workspace_id)
        if workspace.archived_at is not None:
            raise HTTPException(status_code=409, detail="Workspace already archived")

        workspace.archived_at = datetime.now(UTC)
        workspace.api_access_enabled = False
        await self._write_audit(
            action="governance.workspace.archive",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={"workspace_id": workspace_id, "archived_at": "now"},
        )
        await self.session.commit()
        await self.session.refresh(workspace)

        return WorkspaceStatusRead(
            archived_at=workspace.archived_at,
            can_restore=True,
            scrape_paused_at=workspace.scrape_paused_at,
        )

    async def restore_workspace(
        self, workspace_id: int, *, actor_id: UUID | None = None
    ) -> WorkspaceStatusRead:
        """Restore an archived workspace."""
        workspace = await self._get_workspace_or_404(workspace_id)
        if workspace.archived_at is None:
            raise HTTPException(status_code=409, detail="Workspace is not archived")

        workspace.archived_at = None
        workspace.api_access_enabled = True
        await self._write_audit(
            action="governance.workspace.restore",
            actor_id=actor_id,
            subject_id=None,
            diff_payload={"workspace_id": workspace_id, "archived_at": None},
        )
        await self.session.commit()
        await self.session.refresh(workspace)

        return WorkspaceStatusRead(
            archived_at=workspace.archived_at,
            can_restore=False,
            scrape_paused_at=workspace.scrape_paused_at,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_workspace_or_404(self, workspace_id: int) -> Workspace:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await self.session.execute(stmt)
        ws = result.scalars().first()
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return ws

    async def _write_audit(
        self,
        *,
        action: str,
        actor_id: UUID | None,
        subject_id: UUID | str | None,
        diff_payload: dict | None = None,
    ) -> None:
        """Append a governance audit event.

        `subject_id` should be a user/entity UUID when the audit target is a
        principal; otherwise leave it `None` and put the workspace scope inside
        `diff_payload`.
        """
        self.session.add(
            AuditEvent(
                action=action,
                actor_id=actor_id,
                subject_id=subject_id,
                diff_payload=diff_payload,
            )
        )
