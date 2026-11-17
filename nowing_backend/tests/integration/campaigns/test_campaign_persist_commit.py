"""Story 44.1 — commit-proof integration test.

Mục tiêu DUY NHẤT: chứng minh leads + campaign bookkeeping thật sự được
COMMIT (không rollback) khi đi qua route execute với persist=true — bug T0:
``execute_and_persist`` không bao giờ commit → prod roll back.

Khác test_supply_campaign_e2e: db_session fixture của conftest wrap trong
transaction ngoài + savepoint, nên commit của service chỉ release savepoint,
KHÔNG chứng minh được durable. Test này dùng session THẬT từ
``async_session_maker`` (cùng engine/DB của test suite), bypass savepoint.

Ràng buộc: KHÔNG chạm bảng production — mọi row tạo trong workspace riêng
được tạo trong test và xoá sau khi assert (không cần phụ thuộc RLS).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    CampaignLead,
    CampaignRun,
    LeadCampaign,
    PersonalAccessToken,
    User,
    Workspace,
    get_async_session,
)
from app.lead_intelligence.adapters.base import (
    LeadSourceCategory,
    RawLeadRecord,
)
from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator
from app.users import get_auth_context, require_session_context
from app.utils.pat import generate_pat, hash_pat

pytestmark = [pytest.mark.integration]

limiter.enabled = False


# ---------------------------------------------------------------------------
# Fixtures — user/workspace/PAT tạo TRONG session thật + COMMIT thật
# (db_session của conftest là savepoint — PAT không thấy được từ session khác)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def committed_workspace() -> AsyncGenerator[Workspace, None]:
    """User + workspace + membership + PAT committed vào DB thật."""
    from app.db.base import async_session_maker
    from tests.integration.conftest import create_default_roles_and_membership

    token = generate_pat()
    async with async_session_maker() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"44-1-{uuid.uuid4().hex[:8]}@test.nowing.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        space = Workspace(
            name=f"44-1 ws {uuid.uuid4().hex[:8]}",
            user_id=user.id,
        )
        session.add(space)
        await session.flush()
        await create_default_roles_and_membership(session, space.id, user.id)
        space.api_access_enabled = True
        pat = PersonalAccessToken(
            user_id=user.id,
            token_hash=hash_pat(token),
            token_prefix=token[:12],
            label="story-44-1-commit-proof",
            workspace_id=space.id,
            scopes=["leads:read", "leads:write"],
            token_kind="legacy",
        )
        session.add(pat)
        await session.commit()
        try:
            yield space, token
        finally:
            # Cleanup trong session riêng — RLS bypass qua superuser test conn.
            async with async_session_maker() as cleanup:
                await cleanup.execute(
                    delete(LeadCampaign).where(
                        LeadCampaign.workspace_id == space.id
                    )
                )
                await cleanup.execute(
                    delete(PersonalAccessToken).where(
                        PersonalAccessToken.user_id == user.id
                    )
                )
                await cleanup.execute(
                    delete(Workspace).where(Workspace.id == space.id)
                )
                await cleanup.execute(
                    delete(User).where(User.id == user.id)
                )
                await cleanup.commit()


@pytest_asyncio.fixture
async def client_commit_proof(
    committed_workspace: tuple[Workspace, str],
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client với auth chain thật nhưng get_async_session yield SESSION THẬT.

    KHÔNG override get_async_session sang db_session (savepoint) — route nhận
    session thật từ async_session_maker → commit của service là COMMIT THẬT.
    """
    from app.db.base import async_session_maker

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session

    async def passthrough_session(
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        return auth

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[require_session_context] = passthrough_session

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=60.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_search_leads(monkeypatch):
    """Mock search_leads của adapter trong registry — không call mạng."""
    from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry

    leads = [
        RawLeadRecord(
            source_name="muasamcong",
            source_id=f"mua-44-{i}",
            data={
                "tax_id": f"010123456{i}",
                "company_name": f"Công ty 44-{i}",
                "city": "Khánh Hòa",
                "address": "Nha Trang, Khánh Hòa",
                "phone": f"090512345{i}",
            },
            category=LeadSourceCategory.ENTERPRISE,
        )
        for i in range(2)
    ]
    registry = LeadSourceAdapterRegistry.get_default()
    for name in ("muasamcong", "enterprise", "batdongsan", "chotot"):
        adapter = registry.get(name)
        if adapter is not None:
            monkeypatch.setattr(
                adapter, "search_leads", AsyncMock(return_value=leads)
            )
    return leads


@pytest.fixture
def mock_micro_extraction(monkeypatch):
    """Mock micro_batch để không call LLM."""
    from app.lead_intelligence.services.micro_extraction_worker import (
        MicroExtractionWorker,
    )

    monkeypatch.setattr(
        MicroExtractionWorker,
        "micro_batch",
        AsyncMock(return_value=[]),
    )


def _payload(workspace_id: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"Campaign commit proof {uuid.uuid4().hex[:8]}",
        "description": None,
        "workspace_id": workspace_id,
        "direction": "demand",
        "icp_config": {
            "industry": "B2B SaaS",
            "target_roles": ["CEO"],
            "location": None,
            "company_size": None,
            "revenue_range": None,
            "keywords": ["crm"],
        },
        "source_budget_config": {
            "max_per_source": 2,
            "timeout_seconds": 10,
        },
        "launch_config": {"trigger": "immediate"},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_execute_commits_leads_and_campaign_rows(
    client_commit_proof: httpx.AsyncClient,
    committed_workspace: tuple[Workspace, str],
    mock_search_leads,
    mock_micro_extraction,
) -> None:
    """persist=true → leads + 3 bảng campaign durable sau khi request xong."""
    pat_workspace, token = committed_workspace
    ws_id = pat_workspace.id

    resp = await client_commit_proof.post(
        f"/api/v1/workspaces/{ws_id}/campaigns/execute?persist=true",
        json=_payload(ws_id),
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") in ("success", "partial")

    # Session MỚI hoàn toàn — không reuse connection của request.
    from app.db.base import async_session_maker

    async with async_session_maker() as verify:
        campaign = (
            await verify.execute(
                select(LeadCampaign).where(LeadCampaign.workspace_id == ws_id)
            )
        ).scalar_one_or_none()
        assert campaign is not None, "lead_campaigns row missing — commit failed"
        assert campaign.direction == "demand"
        assert campaign.source == "execute"
        assert campaign.status == "completed"

        run = (
            await verify.execute(
                select(CampaignRun).where(CampaignRun.campaign_id == campaign.id)
            )
        ).scalar_one_or_none()
        assert run is not None, "campaign_runs row missing"
        assert run.trigger == "api"
        assert run.status == "succeeded"
        assert run.spec_snapshot is not None

        junction_count = (
            await verify.execute(
                select(func.count())
                .select_from(CampaignLead)
                .where(CampaignLead.campaign_id == campaign.id)
            )
        ).scalar_one()
        assert junction_count >= 1, (
            f"expected >= 1 campaign_leads rows, got {junction_count}"
        )
        roles = {
            r.role
            for r in (
                await verify.execute(
                    select(CampaignLead).where(
                        CampaignLead.campaign_id == campaign.id
                    )
                )
            ).scalars()
        }
        assert roles == {"buyer"}, f"unexpected roles: {roles}"

        # Cleanup — không để rác trong DB test.
        await verify.execute(
            delete(CampaignLead).where(CampaignLead.campaign_id == campaign.id)
        )
        await verify.execute(
            delete(CampaignRun).where(CampaignRun.campaign_id == campaign.id)
        )
        await verify.execute(
            delete(LeadCampaign).where(LeadCampaign.id == campaign.id)
        )
        await verify.commit()


@pytest.mark.asyncio
async def test_persist_false_writes_zero_campaign_rows(
    client_commit_proof: httpx.AsyncClient,
    committed_workspace: tuple[Workspace, str],
    mock_search_leads,
    mock_micro_extraction,
) -> None:
    """persist=false → KHÔNG tạo campaign/run/junction rows."""
    pat_workspace, token = committed_workspace
    ws_id = pat_workspace.id
    payload = _payload(ws_id)

    resp = await client_commit_proof.post(
        f"/api/v1/workspaces/{ws_id}/campaigns/execute?persist=false",
        json=payload,
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text

    from app.db.base import async_session_maker

    async with async_session_maker() as verify:
        count = (
            await verify.execute(
                select(func.count())
                .select_from(LeadCampaign)
                .where(LeadCampaign.workspace_id == ws_id)
            )
        ).scalar_one()
        assert count == 0, f"persist=false wrote {count} campaign rows"
