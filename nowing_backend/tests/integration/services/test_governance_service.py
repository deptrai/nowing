"""Integration tests for GovernanceService (Story 29.6)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    AuditEvent,
    GlobalDncRecord,
    Memory,
    MemorySourceLegalTier,
    MemorySourceType,
    MemoryType,
    Workspace,
    WorkspaceDncRecord,
)
from app.schemas.governance import (
    RetentionPolicyUpdate,
    SourceRiskTierUpdate,
)
from app.services.governance_service import GovernanceService
from tests.integration.conftest import _EMBEDDING_DIM

pytestmark = pytest.mark.integration


# ------------------------------------------------------------------
# AC-2: Retention policy
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_retention_policy_sets_memory_fields(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-2: Retention policy update applies memory fields."""
    svc = GovernanceService(db_session)
    result = await svc.update_retention_policy(
        db_workspace.id,
        RetentionPolicyUpdate(
            memory_auto_archive_enabled=True,
            memory_retention_days=365,
            memory_retention_action="archive",
        ),
        actor_id=db_user.id,
    )
    assert result.memory_retention_days == 365
    assert result.memory_auto_archive_enabled is True


@pytest.mark.asyncio
async def test_update_retention_policy_rejects_below_high_risk_minimum(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-3: Rejects retention below recommended minimum for high-risk source."""
    tier = MemorySourceLegalTier(
        source_type=MemorySourceType.SCRAPER_RUN.value,
        risk_tier="high",
        recommended_retention_days=180,
        notes="Scraped source requires retention",
    )
    db_session.add(tier)
    await db_session.commit()

    svc = GovernanceService(db_session)
    with pytest.raises(Exception) as exc_info:
        await svc.update_retention_policy(
            db_workspace.id,
            RetentionPolicyUpdate(
                memory_auto_archive_enabled=True,
                memory_retention_days=30,
                memory_retention_action="archive",
            ),
            actor_id=db_user.id,
        )
    assert "recommended minimum" in str(exc_info.value).lower()


# ------------------------------------------------------------------
# AC-3: Source risk tiers
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_source_risk_tier_high_pauses_scraping(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-5: High-risk tier sets scrape_paused_at and disables API access."""
    svc = GovernanceService(db_session)
    result = await svc.upsert_source_risk_tier(
        db_workspace.id,
        SourceRiskTierUpdate(
            source_type=MemorySourceType.SCRAPER_RUN,
            risk_tier="high",
            recommended_retention_days=90,
        ),
        actor_id=db_user.id,
    )
    assert result.risk_tier == "high"

    await db_session.refresh(db_workspace)
    assert db_workspace.scrape_paused_at is not None
    assert db_workspace.api_access_enabled is False


# ------------------------------------------------------------------
# AC-5: DNC records
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_dnc_records_marks_superseded_by_global(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-5: DNC list marks workspace records superseded by global entries."""
    phone = "+84901234567"
    from app.lead_intelligence.dnc.normalizer import hash_phone_hmac, normalize_phone_e164

    norm = normalize_phone_e164(phone)
    hmac = hash_phone_hmac(norm)

    # Global DNC entry
    global_rec = GlobalDncRecord(
        record_type="phone",
        value=norm,
        value_hmac=hmac,
        reason="Global blacklist",
        source="admin",
    )
    db_session.add(global_rec)
    await db_session.commit()

    # Workspace DNC entry for same phone
    ws_rec = WorkspaceDncRecord(
        workspace_id=db_workspace.id,
        record_type="phone",
        value=norm,
        value_hmac=hmac,
        reason="Workspace opt-out",
        source="manual",
    )
    db_session.add(ws_rec)
    await db_session.commit()

    svc = GovernanceService(db_session)
    records = await svc.list_dnc_records(db_workspace.id)
    assert len(records) == 1
    assert records[0].superseded_by_global is True


# ------------------------------------------------------------------
# AC-4: Right-to-delete (bulk via BulkOpsService)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_right_to_delete_bulk_dry_run_returns_preview(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-4: Bulk dry-run returns count and preview IDs without deleting."""
    # Seed two memories
    for i in range(2):
        mem = Memory(
            workspace_id=db_workspace.id,
            created_by_id=db_user.id,
            type=MemoryType.SEMANTIC,
            content=f"Memory {i}",
            source_type=MemorySourceType.MANUAL,
            source_id=None,
            confidence=1.0,
            embedding=[0.1] * _EMBEDDING_DIM,
        )
        db_session.add(mem)
    await db_session.commit()

    svc = GovernanceService(db_session)
    from app.schemas.governance import RightToDeleteRequest

    resp = await svc.right_to_delete(
        db_workspace.id,
        RightToDeleteRequest(
            type="bulk",
            source_type=MemorySourceType.MANUAL,
            dry_run=True,
            reason="Bulk purge test",
        ),
        actor_id=db_user.id,
    )
    assert resp.dry_run is True
    assert resp.affected_count == 2
    assert len(resp.preview_memory_ids) == 2


@pytest.mark.asyncio
async def test_right_to_delete_single_memory_executes(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-4: Single memory delete executes and returns 204-equivalent."""
    mem = Memory(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        type=MemoryType.SEMANTIC,
        content="Delete me",
        source_type=MemorySourceType.MANUAL,
        source_id=None,
        confidence=1.0,
        embedding=[0.1] * _EMBEDDING_DIM,
    )
    db_session.add(mem)
    await db_session.commit()

    svc = GovernanceService(db_session)
    from app.schemas.governance import RightToDeleteRequest

    resp = await svc.right_to_delete(
        db_workspace.id,
        RightToDeleteRequest(
            type="single_memory",
            memory_id=mem.id,
            reason="GDPR request",
        ),
        actor_id=db_user.id,
    )
    assert resp.dry_run is False
    assert resp.affected_count == 1


# ------------------------------------------------------------------
# AC-7: Audit log
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_audit_log_scoped_to_workspace(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-7: Audit log returns workspace-scoped events."""
    event = AuditEvent(
        action="governance.test",
        actor_id=db_user.id,
        subject_id=None,
        diff_payload={"workspace_id": db_workspace.id},
    )
    db_session.add(event)
    await db_session.commit()

    svc = GovernanceService(db_session)
    from app.schemas.governance import AuditLogFilter

    logs = await svc.list_audit_log(
        db_workspace.id, AuditLogFilter(action_prefix="governance.")
    )
    assert len(logs) >= 1
    assert logs[0].action == "governance.test"


# ------------------------------------------------------------------
# AC-8: Workspace lifecycle
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_and_restore_workspace(
    db_session: AsyncSession, db_workspace: Workspace, db_user
):
    """AC-8: Archive sets archived_at, restore clears it."""
    svc = GovernanceService(db_session)

    archived = await svc.archive_workspace(db_workspace.id, actor_id=db_user.id)
    assert archived.archived_at is not None
    assert archived.can_restore is True

    restored = await svc.restore_workspace(db_workspace.id, actor_id=db_user.id)
    assert restored.archived_at is None
    assert restored.can_restore is False
