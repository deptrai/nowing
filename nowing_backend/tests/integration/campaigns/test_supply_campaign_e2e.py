"""Story 43.6 — E2E supply campaign qua PAT thật (route → orchestrator → persist).

Giống pattern ``tests/integration/lead_batch/test_pat_batch_ingest_e2e.py``:
auth path thật qua ``Authorization: Bearer`` (``resolve_pat`` →
``AuthContext.pat_auth`` → ``check_permission`` + PAT scope). Khác biệt duy nhất:
campaign routes dùng ``require_session_context`` (từ chối PAT), nên test override
seam này bằng passthrough giữ nguyên ``get_auth_context`` thật.

Không call mạng: ``search_leads`` của 2 adapter supply_eligible (enterprise,
muasamcong) được mock; ``MicroExtractionWorker.micro_batch`` cũng mock để tránh
LLM call.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    Lead,
    PersonalAccessToken,
    User,
    Workspace,
    WorkspaceTable,
    get_async_session,
)
from app.lead_intelligence.adapters.base import LeadSourceCategory, RawLeadRecord
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.services.micro_extraction_worker import MicroExtractionWorker
from app.users import get_auth_context, require_session_context
from app.utils.pat import generate_pat, hash_pat

pytestmark = [pytest.mark.integration]

limiter.enabled = False


# ---------------------------------------------------------------------------
# Fixtures — PAT thật + client qua ASGI với auth chain thật
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pat_workspace(
    db_session: AsyncSession, db_workspace: Workspace
) -> Workspace:
    """Workspace với ``api_access_enabled=True`` — bắt buộc để gated PAT qua được."""
    db_workspace.api_access_enabled = True
    await db_session.flush()
    return db_workspace


@pytest_asyncio.fixture
async def db_pat(
    db_session: AsyncSession, db_user: User, pat_workspace: Workspace
) -> tuple[PersonalAccessToken, str]:
    """PAT thật gắn ``pat_workspace``, scope đủ read/write cho campaign routes."""
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=db_user.id,
        token_hash=hash_pat(token),
        token_prefix=token[:12],
        label="story-43-6-e2e",
        workspace_id=pat_workspace.id,
        scopes=["leads:read", "leads:write"],
        token_kind="legacy",
    )
    db_session.add(pat)
    await db_session.flush()
    return pat, token


@pytest_asyncio.fixture
async def client_real_auth(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """AsyncClient: session override + ``require_session_context`` passthrough.

    Campaign routes yêu cầu interactive session (chặn PAT) — seam đó được mở
    để PAT đi qua, nhưng ``get_auth_context`` KHÔNG override: Bearer PAT vẫn
    resolve thật qua ``resolve_pat``, ``check_permission`` + scope vẫn chạy thật.
    """

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

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


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _supply_payload(workspace_id: int, **overrides: Any) -> dict[str, Any]:
    """FE-faithful supply payload — mirror buildPlanSpec() supply return

    (use-campaign-builder.ts): direction + supply_criteria top-level,
    kèm icp_config zeroed + source_budget_config + launch_config vì
    CampaignCreateInput luôn serialize đủ keys (retro Epic 43 AI-43.2).
    """
    payload: dict[str, Any] = {
        "name": "Tìm NCC phân phối Khánh Hòa",
        "description": None,
        "workspace_id": workspace_id,
        "direction": "supply",
        "supply_criteria": {
            "categories": ["nhà phân phối"],
            "locations": ["Khánh Hòa"],
            "require_tax_id": True,
            "min_rating": 0,
            "require_verified": False,
        },
        "query": None,
        "icp_config": {
            "template": "b2b_saas",
            "target_industries": [],
            "locations": [],
            "company_size_range": "",
            "tech_stack": [],
            "intents": [],
            "negative_keywords": [],
            "reverse_icp_url": None,
            "custom_instructions": None,
            "location_profile": None,
        },
        "source_budget_config": {
            "sources": [],
            "expected_leads_target": 30,
            "max_daily_spend_vnd": None,
            "min_fit_score": 0,
            "min_intent_score": 0,
            "max_contacts_per_lead": 3,
            "exclude_dnc": False,
            "auto_unlock_verified_phones": False,
        },
        "launch_config": {
            "schedule_type": "manual",
            "cron_expression": None,
            "auto_start": False,
            "export_destination": None,
            "notification_webhook": None,
        },
    }
    payload.update(overrides)
    return payload


def _enterprise_record(
    source_id: str, data: dict[str, Any]
) -> RawLeadRecord:
    return RawLeadRecord(
        source_name="enterprise",
        source_id=source_id,
        data=data,
        category=LeadSourceCategory.ENTERPRISE,
    )


def _muasamcong_record(
    source_id: str, data: dict[str, Any]
) -> RawLeadRecord:
    return RawLeadRecord(
        source_name="muasamcong",
        source_id=source_id,
        data=data,
        category=LeadSourceCategory.ENTERPRISE,
    )


# 3 lead giả: 1 kept (đủ MST + company + Khánh Hòa), 2 bị lọc (thiếu MST).
def _fake_enterprise_leads() -> list[RawLeadRecord]:
    return [
        _enterprise_record(
            "ent-001",
            {
                "tax_id": "0101234567",
                "company_name": "Công ty TNHH Phân phối Khánh Hòa",
                "city": "Khánh Hòa",
                "address": "Nha Trang, Khánh Hòa",
                "phone": "0905123456",
            },
        ),
        _enterprise_record(
            "ent-002",
            {
                # Không tax_id → filtered_no_tax_id (require_tax_id=true).
                "company_name": "Công ty TNHH Không MST",
                "city": "Khánh Hòa",
                "address": "Nha Trang, Khánh Hòa",
            },
        ),
        _enterprise_record(
            "ent-003",
            {
                # Sparse identity: không company_name (normalize fallback
                # "Doanh nghiệp đăng ký" vẫn non-empty nhưng KHÔNG tax_id →
                # guard đầu tiên require_tax_id vẫn đếm filtered_no_tax_id).
                "city": "Khánh Hòa",
                "address": "Nha Trang, Khánh Hòa",
            },
        ),
    ]


def _fake_muasamcong_leads() -> list[RawLeadRecord]:
    return [
        _muasamcong_record(
            "msc-001",
            {
                # Không tax_id → filtered_no_tax_id.
                "project_name": "Gói thầu mua sắm văn phòng phẩm",
                "location": "Khánh Hòa",
            },
        ),
    ]


@pytest.fixture
def mock_supply_adapters(monkeypatch: pytest.MonkeyPatch):
    """Mock ``search_leads`` của 2 adapter supply_eligible + micro-LLM worker."""
    registry = LeadSourceAdapterRegistry.get_default()
    enterprise = registry.get("enterprise")
    muasamcong = registry.get("muasamcong")
    monkeypatch.setattr(
        enterprise,
        "search_leads",
        AsyncMock(return_value=_fake_enterprise_leads()),
    )
    monkeypatch.setattr(
        muasamcong,
        "search_leads",
        AsyncMock(return_value=_fake_muasamcong_leads()),
    )
    # Micro-extraction worker gọi LLM — mock fail-soft để không call mạng.
    monkeypatch.setattr(
        MicroExtractionWorker,
        "micro_batch",
        AsyncMock(return_value=[]),
    )


# ---------------------------------------------------------------------------
# T1 — Supply execute e2e (AC-1, AC-2, AC-5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supply_campaign_execute_e2e(
    client_real_auth: httpx.AsyncClient,
    db_session: AsyncSession,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    mock_supply_adapters,
) -> None:
    """POST /campaigns/execute direction='supply' → persist đúng role-tag + counter."""
    _pat, token = db_pat
    payload = _supply_payload(pat_workspace.id)

    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/campaigns/execute",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()

    # AC-2: adapters resolve = supply_eligible only (không batdongsan/chotot).
    source_names = {p["source_name"] for p in result["subtask_plans"]}
    assert source_names == {"enterprise", "muasamcong"}

    # AC-1: counter lọc MST hiện diện + đúng số lead thiếu MST (3 lead).
    counters = result["supply_filter_counters"]
    assert counters["filtered_no_tax_id"] == 3
    assert result["total_discovered"] == 4

    # Persist: đúng 1 lead kept, role-tag qua extra_metadata.
    leads = (
        (await db_session.execute(select(Lead).where(Lead.workspace_id == pat_workspace.id)))
        .scalars()
        .all()
    )
    assert len(leads) == 1
    lead = leads[0]
    assert lead.tax_id == "0101234567"
    assert lead.extra_metadata is not None
    assert lead.extra_metadata.get("lead_role") == "supplier"
    assert lead.extra_metadata.get("campaign_direction") == "supply"
    assert lead.extra_metadata.get("campaign_key") == payload["name"]
    assert lead.extra_metadata.get("visibility") == "private"

    # Auto-table: table_id trỏ WorkspaceTable key='default' (client_id=None).
    assert lead.table_id is not None
    table = (
        await db_session.execute(
            select(WorkspaceTable).where(
                WorkspaceTable.workspace_id == pat_workspace.id,
                WorkspaceTable.id == lead.table_id,
            )
        )
    ).scalar_one_or_none()
    assert table is not None
    assert table.key == "default"


# ---------------------------------------------------------------------------
# T2 — Joint-validation 422 (AC-3), không chạm orchestrator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supply_match_mode_pool_rejected_422(
    client_real_auth: httpx.AsyncClient,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
) -> None:
    """match_mode='pool' (platform phase) → 422 trước khi vào engine."""
    _pat, token = db_pat
    payload = _supply_payload(pat_workspace.id, match_mode="pool")

    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/campaigns/execute",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_supply_missing_supply_criteria_rejected_422(
    client_real_auth: httpx.AsyncClient,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
) -> None:
    """direction='supply' thiếu supply_criteria → 422 (joint validation)."""
    _pat, token = db_pat
    payload = _supply_payload(pat_workspace.id)
    del payload["supply_criteria"]

    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/campaigns/execute",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T3 — Demand regression (AC-4)
# ---------------------------------------------------------------------------


def _demand_payload(workspace_id: int) -> dict[str, Any]:
    """FE-shaped demand payload cũ (không đổi contract)."""
    return {
        "name": "Chiến dịch BĐS Hà Nội",
        "workspace_id": workspace_id,
        "icp_config": {
            "template": "real_estate_investor",
            "target_industries": ["Bất động sản"],
            "locations": ["Hà Nội"],
            "intents": ["BÁN"],
            "custom_instructions": "Mua bán nhà đất chính chủ",
        },
        "source_budget_config": {
            "sources": ["batdongsan", "chotot"],
            "expected_leads_target": 100,
        },
        "launch_config": {"auto_start": True},
    }


@pytest.mark.asyncio
async def test_demand_plan_regression(
    client_real_auth: httpx.AsyncClient,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
) -> None:
    """Demand plan cũ → adapter set demand (batdongsan/chotot), không đổi."""
    _pat, token = db_pat
    payload = _demand_payload(pat_workspace.id)

    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/campaigns/plan",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data["expected_sources"]) == {"batdongsan", "chotot"}
    assert data["estimated_cost_vnd"] == 150000


@pytest.mark.asyncio
async def test_demand_execute_regression(
    client_real_auth: httpx.AsyncClient,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Demand execute persist=false → chạy như cũ (không supply filter/tag)."""
    _pat, token = db_pat
    registry = LeadSourceAdapterRegistry.get_default()
    for name in ("batdongsan", "chotot"):
        adapter = registry.get(name)
        monkeypatch.setattr(
            adapter, "search_leads", AsyncMock(return_value=[])
        )

    payload = _demand_payload(pat_workspace.id)
    resp = await client_real_auth.post(
        f"/api/v1/workspaces/{pat_workspace.id}/campaigns/execute?persist=false",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["total_discovered"] == 0
    assert result["supply_filter_counters"] == {}
