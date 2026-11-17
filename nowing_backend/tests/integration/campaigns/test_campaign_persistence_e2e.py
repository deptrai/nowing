"""Epic 44.4 — E2E per-run usage accounting + vertical #2 proof.

Mirror pattern ``test_supply_campaign_e2e.py`` (Epic 43): PAT thật qua
``Authorization: Bearer`` (``resolve_pat`` → ``AuthContext.pat_auth`` →
``check_permission``), ``require_session_context`` được override passthrough,
adapters mock — không call mạng. Vertical #2: TMĐT supply (masothue path —
``enterprise`` adapter supply_eligible, có ``tax_id`` để qua
``require_tax_id`` default).

Proof targets (spec 44.4):
- ``campaign_runs`` row được tạo + finalize với ``cost_micros`` từ
  ``token_usage`` rows tagged ``campaign_run_id`` (contextvar propagation).
- Junction ``campaign_leads`` role='supplier', đúng số lead post-filter.
- Rename campaign + execute spec tên mới → campaign MỚI, membership mới —
  cũ nguyên vẹn (documented behavior, không merge).
- Re-launch cùng campaign → 2 runs, junction không duplicate
  (UniqueConstraint campaign_id+lead_id).
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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    Lead,
    PersonalAccessToken,
    User,
    Workspace,
    get_async_session,
)
from app.lead_intelligence.adapters.base import LeadSourceCategory, RawLeadRecord
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.services.micro_extraction_worker import MicroExtractionWorker
from app.models.billing import TokenUsage
from app.models.campaigns import CampaignLead, CampaignRun, LeadCampaign
from app.users import get_auth_context, require_session_context
from app.utils.pat import generate_pat, hash_pat

pytestmark = [pytest.mark.integration]

limiter.enabled = False


# ---------------------------------------------------------------------------
# Fixtures — PAT thật + client ASGI auth chain thật (giống Epic 43 e2e)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pat_workspace(
    db_session: AsyncSession, db_workspace: Workspace
) -> Workspace:
    db_workspace.api_access_enabled = True
    await db_session.flush()
    return db_workspace


@pytest_asyncio.fixture
async def db_pat(
    db_session: AsyncSession, db_user: User, pat_workspace: Workspace
) -> tuple[PersonalAccessToken, str]:
    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=db_user.id,
        token_hash=hash_pat(token),
        token_prefix=token[:12],
        label="epic-44-4-e2e",
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
    """Session override + ``require_session_context`` passthrough — PAT resolve thật."""

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
# Payload + mock adapters — vertical #2: TMĐT supply (masothue path)
# ---------------------------------------------------------------------------


def _tmdt_supply_payload(workspace_id: int, name: str, **overrides: Any) -> dict[str, Any]:
    """Supply payload vertical TMĐT (thương mại điện tử) — masothue path.

    ``enterprise`` adapter supply_eligible; leads giả có ``tax_id`` để qua
    ``require_tax_id`` default. Location "Toàn quốc" → bỏ guard location
    (không phụ thuộc geo-profile của vertical BĐS).
    """
    payload: dict[str, Any] = {
        "name": name,
        "description": None,
        "workspace_id": workspace_id,
        "direction": "supply",
        "supply_criteria": {
            "categories": ["người bán sàn TMĐT"],
            "locations": ["Toàn quốc"],
            "require_tax_id": True,
            "min_rating": 0,
            "require_verified": False,
        },
        "query": None,
        "icp_config": {
            "template": "fmcg_distributor",
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


def _enterprise_record(source_id: str, data: dict[str, Any]) -> RawLeadRecord:
    return RawLeadRecord(
        source_name="enterprise",
        source_id=source_id,
        data=data,
        category=LeadSourceCategory.ENTERPRISE,
    )


def _fake_tmdt_leads() -> list[RawLeadRecord]:
    """4 lead TMĐT: 3 kept (đủ MST), 1 thiếu MST bị lọc."""
    return [
        _enterprise_record(
            "tmdt-001",
            {
                "tax_id": "0312345678",
                "company_name": "Công ty TNHH TMĐT An Phát",
                "city": "Hồ Chí Minh",
                "address": "Quận 1, Hồ Chí Minh",
                "phone": "0909111222",
            },
        ),
        _enterprise_record(
            "tmdt-002",
            {
                "tax_id": "0312345679",
                "company_name": "Công ty CP TMĐT Việt thương",
                "city": "Hà Nội",
                "address": "Cầu Giấy, Hà Nội",
            },
        ),
        _enterprise_record(
            "tmdt-003",
            {
                "tax_id": "0312345680",
                "company_name": "Hộ kinh doanh Meo Mart",
                "city": "Đà Nẵng",
                "address": "Hải Châu, Đà Nẵng",
            },
        ),
        _enterprise_record(
            "tmdt-004",
            {
                # Không tax_id → filtered_no_tax_id.
                "company_name": "Shop không MST",
                "city": "Hồ Chí Minh",
            },
        ),
    ]


@pytest.fixture
def mock_tmdt_adapters(monkeypatch: pytest.MonkeyPatch):
    """Mock ``search_leads`` cả 2 adapter supply_eligible + micro-LLM worker.

    Vertical #2 = TMĐT: enterprise giả lập seller sàn TMĐT (có MST),
    muasamcong trả rỗng — không call mạng thật.
    """
    registry = LeadSourceAdapterRegistry.get_default()
    enterprise = registry.get("enterprise")
    muasamcong = registry.get("muasamcong")
    monkeypatch.setattr(
        enterprise,
        "search_leads",
        AsyncMock(return_value=_fake_tmdt_leads()),
    )
    monkeypatch.setattr(
        muasamcong,
        "search_leads",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        MicroExtractionWorker,
        "micro_batch",
        AsyncMock(return_value=[]),
    )


# ---------------------------------------------------------------------------
# USAGE_TAG / E2E_SUPPLY — run + junction + cost_micros qua /execute thật
# ---------------------------------------------------------------------------


async def _execute(
    client: httpx.AsyncClient,
    workspace_id: int,
    token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/campaigns/execute",
        headers=_headers(token),
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_tmdt_supply_run_accounting_e2e(
    client_real_auth: httpx.AsyncClient,
    db_session: AsyncSession,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    mock_tmdt_adapters,
) -> None:
    """E2E_SUPPLY + USAGE_TAG + COST_ZERO: TMĐT supply execute persist.

    Scrape-only (micro_batch mock rỗng → 0 LLM usage) → ``cost_micros = 0``
    là đúng (usage ≠ charge). Run row + junction role='supplier' + leads MST.
    """
    _pat, token = db_pat
    payload = _tmdt_supply_payload(pat_workspace.id, "NCC TMĐT đa kênh")

    result = await _execute(client_real_auth, pat_workspace.id, token, payload)

    # Run được tạo + finalize (route trả campaign_run_id — Epic 44.1 tagging).
    run_id = result["campaign_run_id"]
    assert run_id is not None
    campaign_id = result["campaign_id"]
    assert campaign_id is not None

    run = await db_session.get(CampaignRun, run_id)
    assert run is not None
    assert run.status == "succeeded"
    assert run.finished_at is not None
    # COST_ZERO: scrape-only run — khẳng định 0 usage row tagged run
    # (không chỉ ngầm qua cost_micros).
    tagged_count = (
        await db_session.execute(
            select(func.count())
            .select_from(TokenUsage)
            .where(
                TokenUsage.call_details.op("->>")("campaign_run_id") == run_id
            )
        )
    ).scalar_one()
    assert tagged_count == 0
    assert run.cost_micros == 0

    # Adapters: vertical TMĐT path → enterprise + muasamcong (đều
    # supply_eligible); muasamcong thật không trả lead vì chỉ mock enterprise
    # search_leads.
    source_names = {p["source_name"] for p in result["subtask_plans"]}
    assert source_names == {"enterprise", "muasamcong"}

    # Post-filter: 3 kept, 1 thiếu MST.
    counters = result["supply_filter_counters"]
    assert counters["filtered_no_tax_id"] == 1
    assert result["total_discovered"] == 4

    # Junction role='supplier' đúng số lead post-filter.
    junctions = (
        (
            await db_session.execute(
                select(CampaignLead).where(CampaignLead.campaign_id == campaign_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(junctions) == 3
    assert all(j.role == "supplier" for j in junctions)
    # result JSON trả str — so sánh ở dạng str.
    assert all(str(j.run_id) == run_id for j in junctions)

    # Leads persisted với MST + supply tags.
    leads = (
        (
            await db_session.execute(
                select(Lead).where(Lead.workspace_id == pat_workspace.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(leads) == 3
    assert all(lead.tax_id for lead in leads)
    assert all(
        lead.extra_metadata.get("lead_role") == "supplier" for lead in leads
    )


# ---------------------------------------------------------------------------
# RELAUNCH_NODUP — execute lặp cùng spec → 2 runs, junction không dup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relaunch_same_spec_no_duplicate_membership(
    client_real_auth: httpx.AsyncClient,
    db_session: AsyncSession,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    mock_tmdt_adapters,
) -> None:
    _pat, token = db_pat
    payload = _tmdt_supply_payload(pat_workspace.id, "NCC TMĐT re-launch")

    first = await _execute(client_real_auth, pat_workspace.id, token, payload)
    second = await _execute(client_real_auth, pat_workspace.id, token, payload)

    assert first["campaign_id"] == second["campaign_id"]
    assert first["campaign_run_id"] != second["campaign_run_id"]

    # 2 runs trên cùng campaign, đều succeeded.
    runs = (
        (
            await db_session.execute(
                select(CampaignRun)
                .where(CampaignRun.campaign_id == first["campaign_id"])
                .order_by(CampaignRun.started_at)
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 2
    assert {r.status for r in runs} == {"succeeded"}

    # Junction không duplicate nhờ UniqueConstraint(campaign_id, lead_id).
    lead_count = (
        await db_session.execute(
            select(func.count())
            .select_from(CampaignLead)
            .where(CampaignLead.campaign_id == first["campaign_id"])
        )
    ).scalar_one()
    assert lead_count == 3


# ---------------------------------------------------------------------------
# RENAME_SURVIVES — rename + execute spec tên mới → campaign mới, cũ nguyên
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_then_new_spec_creates_new_campaign(
    client_real_auth: httpx.AsyncClient,
    db_session: AsyncSession,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    mock_tmdt_adapters,
) -> None:
    _pat, token = db_pat
    old_name = "NCC TMĐT phiên bản 1"

    first = await _execute(
        client_real_auth,
        pat_workspace.id,
        token,
        _tmdt_supply_payload(pat_workspace.id, old_name),
    )
    old_campaign_id = first["campaign_id"]

    # Rename trực tiếp trên campaign row (44.2 PATCH chưa trong scope 44.4 —
    # spec: "PATCH hoặc trực tiếp update name nếu 44.2 chưa có").
    campaign = await db_session.get(LeadCampaign, old_campaign_id)
    assert campaign is not None
    campaign.name = "NCC TMĐT phiên bản 1 (đã đổi tên)"
    await db_session.flush()

    # Execute spec MỚI với tên gốc → campaign MỚI (unique key name mới).
    second = await _execute(
        client_real_auth,
        pat_workspace.id,
        token,
        _tmdt_supply_payload(pat_workspace.id, old_name),
    )
    new_campaign_id = second["campaign_id"]
    assert new_campaign_id != old_campaign_id

    # Campaign cũ nguyên vẹn: membership cũ không bị merge sang campaign mới.
    old_junctions = (
        (
            await db_session.execute(
                select(CampaignLead).where(
                    CampaignLead.campaign_id == old_campaign_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(old_junctions) == 3

    new_junctions = (
        (
            await db_session.execute(
                select(CampaignLead).where(
                    CampaignLead.campaign_id == new_campaign_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(new_junctions) == 3


# ---------------------------------------------------------------------------
# USAGE_TAG + COST_FINALIZE — record_token_usage trong run context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_usage_tagged_and_finalized_into_cost_micros(
    client_real_auth: httpx.AsyncClient,
    db_session: AsyncSession,
    pat_workspace: Workspace,
    db_pat: tuple[PersonalAccessToken, str],
    mock_tmdt_adapters,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """USAGE_TAG + COST_FINALIZE end-to-end trong 1 execute request.

    Mock ``MicroExtractionWorker.micro_batch`` bằng hàm cục bộ ghi 3 usage
    rows qua ``record_token_usage`` (bản thật, không patch) trong lúc
    orchestrator chạy — contextvar do ``execute_and_persist`` set còn hiệu
    lực → rows tự tag ``campaign_run_id`` → finalize sum thành cost_micros.
    Wrapper ``_record_with_usage`` chỉ để bắt record đã ghi (assert), không
    thay đổi hành vi.
    """
    from app.services import token_tracking_service

    real_record = token_tracking_service.record_token_usage
    recorded: list[TokenUsage] = []

    async def _record_with_usage(*args: Any, **kwargs: Any) -> Any:
        # Gọi trong run context — contextvar do execute_and_persist set.
        record = await real_record(*args, **kwargs)
        if record is not None:
            recorded.append(record)
        return record

    async def _fake_batch(*args: Any, **kwargs: Any) -> list:
        # 3 "LLM call" diễn ra trong run context — mỗi call 1 usage row.
        for cost in (1000, 2500, 6500):
            await _record_with_usage(
                db_session,
                usage_type="lead_gen",
                workspace_id=pat_workspace.id,
                cost_micros=cost,
                call_details={"model": "gpt-4o-mini"},
            )
        return []

    registry = LeadSourceAdapterRegistry.get_default()
    enterprise = registry.get("enterprise")
    monkeypatch.setattr(
        enterprise,
        "search_leads",
        AsyncMock(return_value=_fake_tmdt_leads()),
    )
    monkeypatch.setattr(MicroExtractionWorker, "micro_batch", _fake_batch)

    _pat, token = db_pat
    result = await _execute(
        client_real_auth,
        pat_workspace.id,
        token,
        _tmdt_supply_payload(pat_workspace.id, "NCC TMĐT có usage"),
    )
    run_id = result["campaign_run_id"]

    # 3 usage rows được ghi, mỗi row tự tag campaign_run_id qua contextvar.
    assert len(recorded) == 3
    assert all(
        r.call_details is not None
        and r.call_details.get("campaign_run_id") == run_id
        for r in recorded
    )
    # USAGE_NOTAG: call ngoài run context không tag.
    outside = await token_tracking_service.record_token_usage(
        db_session,
        usage_type="lead_gen",
        workspace_id=pat_workspace.id,
        cost_micros=99,
        call_details={"model": "gpt-4o-mini"},
    )
    assert outside is not None
    assert "campaign_run_id" not in (outside.call_details or {})

    run = await db_session.get(CampaignRun, run_id)
    assert run is not None
    assert run.cost_micros == 10_000
