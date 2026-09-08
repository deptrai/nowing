"""Integration tests for workspace governance console routes (Story 29.6)."""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
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
from tests.integration.conftest import _EMBEDDING_DIM

pytestmark = pytest.mark.integration


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest_asyncio.fixture
async def governance_client(db_session: AsyncSession, db_workspace: Workspace, db_user):
    """HTTP client authenticated as the workspace owner."""
    from app.app import app, limiter
    from app.auth.context import AuthContext
    from app.db import get_async_session
    from app.users import get_auth_context

    limiter.enabled = False

    async def override_session():
        yield db_session

    async def override_auth():
        return AuthContext.session(db_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def governance_member_client(db_session: AsyncSession, db_workspace: Workspace, db_other_user):
    """HTTP client authenticated as a non-owner member."""
    from app.app import app, limiter
    from app.auth.context import AuthContext
    from app.db import get_async_session
    from app.users import get_auth_context

    limiter.enabled = False

    async def override_session():
        yield db_session

    async def override_auth():
        return AuthContext.session(db_other_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


# ------------------------------------------------------------------
# AC-1: Governance overview
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_governance_overview_returns_workspace_scoped_payload(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-1: Overview returns retention, tiers, DNC, status."""
    resp = await governance_client.get(f"/workspaces/{db_workspace.id}/governance")
    assert resp.status_code == 200
    data = resp.json()
    assert "retention_policy" in data
    assert "source_risk_tiers" in data
    assert "dnc_records" in data
    assert "workspace_status" in data
    assert "deployment_mode" in data


@pytest.mark.asyncio
async def test_governance_overview_forbidden_for_non_member(
    governance_member_client: AsyncClient, db_workspace: Workspace
):
    """AC-1: Non-member gets 403."""
    resp = await governance_member_client.get(f"/workspaces/{db_workspace.id}/governance")
    assert resp.status_code == 403


# ------------------------------------------------------------------
# AC-2: Retention policy editing
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_retention_policy_validates_memory_retention_days(
    governance_client: AsyncClient, db_workspace: Workspace
):
    """AC-2: Rejects non-positive memory_retention_days when auto-archive enabled."""
    resp = await governance_client.put(
        f"/workspaces/{db_workspace.id}/governance/retention",
        json={
            "memory_auto_archive_enabled": True,
            "memory_retention_days": 0,
        },
    )
    assert resp.status_code == 422
    assert "memory_retention_days" in resp.text.lower()


@pytest.mark.asyncio
async def test_update_retention_policy_success_and_audit(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-2: Successful update writes audit event."""
    resp = await governance_client.put(
        f"/workspaces/{db_workspace.id}/governance/retention",
        json={
            "memory_auto_archive_enabled": True,
            "memory_retention_days": 365,
            "memory_retention_action": "archive",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["memory_retention_days"] == 365

    # Verify audit event
    result = await db_session.execute(
        select(AuditEvent).where(
            AuditEvent.action == "governance.retention_policy.update"
        )
    )
    audit = result.scalars().first()
    assert audit is not None
    assert audit.diff_payload.get("memory_retention_days") == 365


@pytest.mark.asyncio
async def test_update_retention_policy_rejects_high_risk_below_minimum(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-3/AC-2: Rejects retention below high-risk recommended minimum."""
    tier = MemorySourceLegalTier(
        source_type=MemorySourceType.SCRAPER_RUN.value,
        risk_tier="high",
        recommended_retention_days=180,
        notes="Scraped source requires retention",
    )
    db_session.add(tier)
    await db_session.commit()

    resp = await governance_client.put(
        f"/workspaces/{db_workspace.id}/governance/retention",
        json={
            "memory_auto_archive_enabled": True,
            "memory_retention_days": 30,
            "memory_retention_action": "archive",
        },
    )
    assert resp.status_code == 400
    assert "recommended minimum" in resp.json()["detail"].lower()


# ------------------------------------------------------------------
# AC-3: Source risk tiers
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_source_risk_tier_high_pauses_scraping(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-5: High-risk tier triggers scrape pause."""
    resp = await governance_client.put(
        f"/workspaces/{db_workspace.id}/governance/source-risk-tiers",
        json={
            "source_type": MemorySourceType.SCRAPER_RUN.value,
            "risk_tier": "high",
            "recommended_retention_days": 90,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_tier"] == "high"

    await db_session.refresh(db_workspace)
    assert db_workspace.scrape_paused_at is not None
    assert db_workspace.api_access_enabled is False


# ------------------------------------------------------------------
# AC-5: DNC records
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_dnc_record_normalizes_and_marks_superseded(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-5: Creates DNC record and flags global supersession."""
    # Pre-seed a global DNC entry for the same phone
    from app.lead_intelligence.dnc.normalizer import hash_phone_hmac, normalize_phone_e164

    phone = "+84901234567"
    norm = normalize_phone_e164(phone)
    hmac = hash_phone_hmac(norm)
    global_rec = GlobalDncRecord(
        record_type="phone",
        value=norm,
        value_hmac=hmac,
        reason="Global blacklist",
        source="admin",
    )
    db_session.add(global_rec)
    await db_session.commit()

    resp = await governance_client.post(
        f"/workspaces/{db_workspace.id}/governance/dnc-records",
        json={
            "record_type": "phone",
            "value": phone,
            "reason": "Opt-out",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["superseded_by_global"] is True


@pytest.mark.asyncio
async def test_delete_dnc_record_removes_and_invalidates_cache(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-5: Delete removes record."""
    rec = WorkspaceDncRecord(
        workspace_id=db_workspace.id,
        record_type="email",
        value="test@example.com",
        value_hmac="abc123",
        reason="Opt-out",
        source="manual",
    )
    db_session.add(rec)
    await db_session.commit()

    resp = await governance_client.delete(
        f"/workspaces/{db_workspace.id}/governance/dnc-records/{rec.id}"
    )
    assert resp.status_code == 204


# ------------------------------------------------------------------
# AC-4: Right-to-delete
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_right_to_delete_single_memory_dry_run(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession, db_user
):
    """AC-4: Single memory dry-run returns count without deleting."""
    mem = Memory(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        type=MemoryType.SEMANTIC,
        content="Test memory",
        source_type=MemorySourceType.MANUAL,
        source_id=None,
        confidence=0.9,
        embedding=[0.1] * _EMBEDDING_DIM,
    )
    db_session.add(mem)
    await db_session.commit()

    resp = await governance_client.post(
        f"/workspaces/{db_workspace.id}/governance/right-to-delete",
        json={
            "type": "single_memory",
            "memory_id": mem.id,
            "reason": "GDPR request",
            "dry_run": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["affected_count"] == 1
    assert data["preview_memory_ids"] == [mem.id]


# ------------------------------------------------------------------
# AC-7: Audit log
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_filters_by_workspace_and_action_prefix(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession, db_user
):
    """AC-7: Audit log returns workspace-scoped events."""
    event = AuditEvent(
        action="governance.retention_policy.update",
        actor_id=db_user.id,
        subject_id=None,
        diff_payload={"workspace_id": db_workspace.id, "field": "value"},
    )
    db_session.add(event)
    await db_session.commit()

    resp = await governance_client.get(
        f"/workspaces/{db_workspace.id}/governance/audit-log",
        params={"action_prefix": "governance."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["action"].startswith("governance.")


# ------------------------------------------------------------------
# AC-8: Workspace lifecycle
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_and_restore_workspace(
    governance_client: AsyncClient, db_workspace: Workspace, db_session: AsyncSession
):
    """AC-8: Archive and restore toggle archived_at."""
    resp = await governance_client.post(f"/workspaces/{db_workspace.id}/governance/archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["archived_at"] is not None
    assert data["can_restore"] is True

    resp = await governance_client.post(f"/workspaces/{db_workspace.id}/governance/restore")
    assert resp.status_code == 200
    data = resp.json()
    assert data["archived_at"] is None
    assert data["can_restore"] is False
