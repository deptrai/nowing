"""Comprehensive tests for Lead Gen Enterprise Readiness Epic.

Stories covered:
1. Campaign Builder UX: REST endpoints (presets, reverse-ICP, plan, execute)
2. Orchestrator Performance: Latency tracking, source breakdown, dedup rate, graceful degradation
3. CRM & Conversion Tracking: OutcomeEvent persistence, Memory update, conversion listing & REST routes
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    CrmConnection,
    Lead,
    Memory,
    OutcomeEvent,
    User,
    Workspace,
)
from app.lead_intelligence.adapters.base import (
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.campaign.presets import (
    VerticalPresetId,
    generate_reverse_icp,
    get_vertical_preset,
    list_vertical_presets,
)
from app.lead_intelligence.campaign.schemas import (
    CampaignSpec,
    ICPCriteria,
    SourceBudget,
)
from app.lead_intelligence.crm.schemas import CrmConversionLogInput
from app.lead_intelligence.crm.service import CrmSyncService
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)
from app.app import app
from app.db import get_async_session
from app.users import require_session_context

pytestmark = [pytest.mark.integration]


@pytest.fixture
def override_auth_owner(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Override auth and session dependencies to provide owner context and db session."""
    auth = AuthContext.session(user=db_user)

    async def _mock_auth():
        return auth

    async def _mock_session():
        yield db_session

    app.dependency_overrides[require_session_context] = _mock_auth
    app.dependency_overrides[get_async_session] = _mock_session
    yield auth
    app.dependency_overrides.pop(require_session_context, None)
    app.dependency_overrides.pop(get_async_session, None)


class TestCampaignBuilderEndpoints:
    """Test REST API routes for Campaign Builder UX (Story 1 / Story 25.5)."""

    @pytest.mark.asyncio
    async def test_list_presets_endpoint(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """GET /workspaces/{id}/campaigns/presets returns standard vertical presets."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/presets"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 5
            ids = [p["id"] for p in data]
            assert "b2b_saas" in ids
            assert "real_estate_investor" in ids
            assert "recruitment_agency" in ids
            assert "gov_tender_contractor" in ids
            assert "fmcg_distributor" in ids

    @pytest.mark.asyncio
    async def test_get_single_preset_endpoint(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """GET /workspaces/{id}/campaigns/presets/{preset_id} retrieves preset detail."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/presets/b2b_saas"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "b2b_saas"
            assert "icp_criteria" in data
            assert len(data["icp_criteria"]["target_industries"]) > 0

    @pytest.mark.asyncio
    async def test_reverse_icp_endpoint(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """POST /workspaces/{id}/campaigns/reverse-icp infers vertical and keywords."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/reverse-icp",
                json={
                    "url": "https://batdongsan-vin.com",
                    "description": "Chuyên bán căn hộ chung cư cao cấp Vinhomes Smart City",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["suggested_template"] == "real_estate_investor"
            assert "icp_criteria" in data
            assert "target_keywords" in data["icp_criteria"]
            assert len(data["recommended_sources"]) > 0

    @pytest.mark.asyncio
    async def test_plan_campaign_endpoint(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """POST /workspaces/{id}/campaigns/plan previews subtask breakdown."""
        payload = {
            "name": "B2B SaaS Growth Campaign",
            "workspace_id": db_workspace.id,
            "target_sources": ["vn_jobs", "job_market"],
            "source_budgets": [
                {"source_name": "vn_jobs", "max_leads": 25, "priority": 1},
                {"source_name": "job_market", "max_leads": 15, "priority": 2},
            ],
            "max_total_leads": 40,
            "icp_criteria": {
                "target_locations": ["Hà Nội", "Hồ Chí Minh"],
                "target_keywords": ["python", "saas"],
            },
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/plan",
                json=payload,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["campaign_name"] == "B2B SaaS Growth Campaign"
            assert data["total_planned_sources"] == 2
            assert len(data["subtasks"]) == 2
            assert data["subtasks"][0]["limit"] == 25

    @pytest.mark.asyncio
    async def test_execute_campaign_endpoint(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """POST /workspaces/{id}/campaigns/execute triggers orchestrator execution."""
        payload = {
            "name": "Test Quick Run",
            "workspace_id": db_workspace.id,
            "target_sources": ["batdongsan"],
            "max_total_leads": 10,
            "icp_criteria": {
                "target_locations": ["Đà Nẵng"],
            },
        }
        mock_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=5,
            total_deduplicated=4,
            leads=[],
            degraded_sources=[],
            execution_time_ms=120.5,
            source_latency_ms={"batdongsan": 115.2},
            deduplication_rate=0.2,
        )

        with patch.object(
            LeadGenOrchestrator,
            "execute_and_persist",
            AsyncMock(return_value=mock_result),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    f"/api/v1/workspaces/{db_workspace.id}/campaigns/execute?persist=true",
                    json=payload,
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "completed"
                assert data["total_discovered"] == 5
                assert data["total_deduplicated"] == 4
                assert data["execution_time_ms"] == 120.5
                assert data["deduplication_rate"] == 0.2


class TestOrchestratorPerformanceAndTelemetry:
    """Test performance, latency tracking, and metrics in LeadGenOrchestrator (Story 2 / Story 26.5)."""

    @pytest.mark.asyncio
    async def test_orchestrator_latency_and_metrics_tracking(self) -> None:
        """Orchestrator should accurately measure total execution_time_ms and per-source latency."""
        orchestrator = LeadGenOrchestrator()

        raw_records_1 = [
            RawLeadRecord(
                source_name="src_fast",
                source_id="f1",
                data={"title": "Tech Lead", "phone": "0901112233", "location": "Hanoi"},
            ),
            RawLeadRecord(
                source_name="src_fast",
                source_id="f2",
                data={"title": "Backend Dev", "phone": "0901112234", "location": "Hanoi"},
            ),
        ]
        raw_records_2 = [
            RawLeadRecord(
                source_name="src_slow",
                source_id="s1",
                data={"title": "Tech Lead duplicate", "phone": "0901112233", "location": "Hanoi"},
            ),
        ]

        mock_adapter_fast = MagicMock()
        mock_adapter_fast.source_name = "src_fast"
        mock_adapter_fast.category = LeadSourceCategory.JOB_MARKET
        mock_adapter_fast.last_execution_status = "ok"
        mock_adapter_fast.search_leads = AsyncMock(return_value=raw_records_1)
        mock_adapter_fast.normalize_lead.side_effect = lambda raw: NormalizedLead(
            source_name=raw.source_name,
            source_id=raw.source_id,
            title=raw.data.get("title"),
            primary_phone=raw.data.get("phone"),
            city=raw.data.get("location"),
            raw_data=raw.data,
        )

        mock_adapter_slow = MagicMock()
        mock_adapter_slow.source_name = "src_slow"
        mock_adapter_slow.category = LeadSourceCategory.JOB_MARKET
        mock_adapter_slow.last_execution_status = "ok"
        mock_adapter_slow.search_leads = AsyncMock(return_value=raw_records_2)
        mock_adapter_slow.normalize_lead.side_effect = lambda raw: NormalizedLead(
            source_name=raw.source_name,
            source_id=raw.source_id,
            title=raw.data.get("title"),
            primary_phone=raw.data.get("phone"),
            city=raw.data.get("location"),
            raw_data=raw.data,
        )

        with patch.object(
            orchestrator.registry,
            "resolve_adapters_for_intent",
            return_value=[mock_adapter_fast, mock_adapter_slow],
        ):
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=99,
                query="developer",
            )

            assert isinstance(result, LeadGenOrchestratorResult)
            assert result.status == "completed"
            assert result.total_discovered == 3
            # Dedup merges records with identical phone 0901112233
            assert result.total_deduplicated == 2
            assert result.execution_time_ms > 0.0
            assert "src_fast" in result.source_latency_ms
            assert "src_slow" in result.source_latency_ms
            assert result.deduplication_rate > 0.0

    @pytest.mark.asyncio
    async def test_orchestrator_graceful_degradation_on_timeout(self) -> None:
        """When an adapter times out, orchestrator gracefully records degraded source."""
        import asyncio

        orchestrator = LeadGenOrchestrator()

        async def _slow_search(*args, **kwargs):
            await asyncio.sleep(0.5)
            return []

        mock_slow_adapter = MagicMock()
        mock_slow_adapter.source_name = "timeout_adapter"
        mock_slow_adapter.category = LeadSourceCategory.JOB_MARKET
        mock_slow_adapter.search_leads = AsyncMock(side_effect=_slow_search)

        with patch.object(
            orchestrator.registry,
            "resolve_adapters_for_intent",
            return_value=[mock_slow_adapter],
        ):
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=99,
                query="engineer",
                adapter_timeout_seconds=0.05,
            )

            assert result.status == "degraded"
            assert "timeout_adapter" in result.degraded_sources
            assert len(result.leads) == 0


class TestCrmAndConversionTracking:
    """Test CRM outcome conversion tracking, attribution, and memory context (Story 3 / Story 27.5)."""

    @pytest.mark.asyncio
    async def test_crm_conversion_service_and_memory(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CrmSyncService.log_conversion should persist OutcomeEvent and create context Memory."""
        from app.config import config
        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-crm-conversion-secure-32chars")

        lead = Lead(
            workspace_id=db_workspace.id,
            company_name="Acme Viet Nam",
            domain="acme.vn",
            location="Hà Nội",
            source="batdongsan",
        )
        db_session.add(lead)
        await db_session.flush()

        auth = AuthContext.session(user=db_user)
        crm_service = CrmSyncService(db_session)

        conversion_input = CrmConversionLogInput(
            lead_id=lead.id,
            event_type="outcome_deal_won",
            attribution="inbound_campaign",
            cost_micros=500000,
            metadata={"contract_value_vnd": 50000000, "sales_rep": "Nguyen Van A"},
        )

        outcome_event = await crm_service.log_conversion(
            auth=auth,
            workspace_id=db_workspace.id,
            conversion_data=conversion_input,
        )

        assert outcome_event is not None
        assert outcome_event.id is not None
        assert outcome_event.event_type == "outcome_deal_won"
        assert outcome_event.attribution == "inbound_campaign"
        assert outcome_event.cost_micros == 500000
        assert outcome_event.outcome_metadata["contract_value_vnd"] == 50000000

        # Verify Memory creation
        mem_result = await db_session.execute(
            select(Memory).where(Memory.source_uuid == outcome_event.id)
        )
        mem = mem_result.scalars().first()
        assert mem is not None
        assert "Acme Viet Nam" in mem.content
        assert "crm_conversion" in mem.tags

        # Verify list_conversions
        conversions = await crm_service.list_conversions(
            auth=auth,
            workspace_id=db_workspace.id,
            lead_id=lead.id,
        )
        assert len(conversions) == 1
        assert conversions[0].id == outcome_event.id

    @pytest.mark.asyncio
    async def test_crm_conversion_rest_routes(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
        override_auth_owner: AuthContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test POST and GET /workspaces/{id}/crm/conversions REST endpoints."""
        from app.config import config
        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-crm-routes-secure-32chars")

        lead = Lead(
            workspace_id=db_workspace.id,
            company_name="Beta Logistics Corp",
            domain="betalogistics.vn",
            location="Hồ Chí Minh",
            source="vn_jobs",
        )
        db_session.add(lead)
        await db_session.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 1. Log conversion via POST
            post_resp = await client.post(
                f"/api/v1/workspaces/{db_workspace.id}/crm/conversions",
                json={
                    "lead_id": str(lead.id),
                    "event_type": "outcome_meeting_booked",
                    "attribution": "zns_followup",
                    "cost_micros": 200000,
                    "metadata": {"channel": "zalo_zns"},
                },
            )
            assert post_resp.status_code == 200
            post_data = post_resp.json()
            assert post_data["lead_id"] == str(lead.id)
            assert post_data["event_type"] == "outcome_meeting_booked"
            assert post_data["attribution"] == "zns_followup"

            # 2. Query conversions via GET
            get_resp = await client.get(
                f"/api/v1/workspaces/{db_workspace.id}/crm/conversions?lead_id={lead.id}"
            )
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert isinstance(get_data, list)
            assert len(get_data) >= 1
            assert get_data[0]["event_type"] == "outcome_meeting_booked"
