"""Integration tests for Signal-First Campaign Planning and Dynamic Routing Architecture."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, Workspace, WorkspaceTable
from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.campaign.planner import LeadGenPlanner
from app.lead_intelligence.campaign.schemas import (
    CampaignSpec,
    ICPCriteria,
    ScheduleConfig,
    SourceBudget,
)
from app.lead_intelligence.confidence.gate import ConfidenceGate
from app.lead_intelligence.confidence.schemas import CompositeConfidenceResult
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)

pytestmark = [pytest.mark.integration]


class TestSignalFirstCampaignPlanning:
    """Test dynamic routing, planning, and ICP filtering for campaign specs."""

    def test_dynamic_routing_by_signal_and_icp(self) -> None:
        """Dynamic routing should resolve adapters accurately based on ICP vertical and buying signals."""
        registry = LeadSourceAdapterRegistry.get_default()

        # Case 1: Hiring signal and Job market ICP
        hiring_spec = CampaignSpec(
            name="Tech Recruitment Campaign",
            workspace_id=1,
            signal_triggers=["hiring", "recruitment"],
            icp_criteria=ICPCriteria(
                target_categories=[LeadSourceCategory.JOB_MARKET],
                target_industries=["Information Technology", "Software"],
            ),
        )
        adapters = registry.resolve_adapters_for_campaign(hiring_spec)
        categories = {a.category for a in adapters}
        assert LeadSourceCategory.JOB_MARKET in categories
        assert all(a.category == LeadSourceCategory.JOB_MARKET for a in adapters)

        # Case 2: Tender/procurement signal
        tender_spec = CampaignSpec(
            name="Public Bidding Campaign",
            workspace_id=1,
            signal_triggers=["tender", "procurement"],
        )
        tender_adapters = registry.resolve_adapters_for_campaign(tender_spec)
        assert any(a.source_name == "muasamcong" for a in tender_adapters)

        # Case 3: Real estate signal
        bds_spec = CampaignSpec(
            name="Real Estate Hanoi",
            workspace_id=1,
            signal_triggers=["real_estate"],
            icp_criteria=ICPCriteria(
                target_locations=["Hà Nội"],
                target_keywords=["chung cư"],
            ),
        )
        bds_adapters = registry.resolve_adapters_for_campaign(bds_spec)
        assert any(a.source_name == "batdongsan" for a in bds_adapters)
        assert any(a.source_name == "chotot" for a in bds_adapters)

    def test_planner_creates_subtasks_with_budgets(self) -> None:
        """LeadGenPlanner should decompose CampaignSpec into bounded SubTaskPlan items."""
        registry = LeadSourceAdapterRegistry.get_default()
        planner = LeadGenPlanner(registry=registry)

        spec = CampaignSpec(
            name="Enterprise & Jobs Multi-Source Campaign",
            workspace_id=10,
            target_sources=["enterprise", "muasamcong"],
            source_budgets=[
                SourceBudget(source_name="enterprise", max_leads=30, priority=1),
                SourceBudget(source_name="muasamcong", max_leads=20, priority=2),
            ],
            max_total_leads=40,
            icp_criteria=ICPCriteria(
                target_locations=["Hồ Chí Minh"],
                target_keywords=["phần mềm"],
            ),
        )

        subtasks, expected_sources = planner.plan_from_campaign(spec)
        assert "enterprise" in expected_sources
        assert "muasamcong" in expected_sources
        assert len(subtasks) == 2

        ent_task = next(t for t in subtasks if t.source_name == "enterprise")
        assert ent_task.limit == 30
        assert ent_task.priority == 1
        assert ent_task.filters["target_locations"] == ["Hồ Chí Minh"]

        proc_task = next(t for t in subtasks if t.source_name == "muasamcong")
        assert proc_task.limit == 20
        assert proc_task.priority == 2

    def test_composite_confidence_gate_calculation(self) -> None:
        """Composite confidence gate should properly calculate 0.4*schema + 0.4*icp + 0.2*intent."""
        lead = NormalizedLead(
            source_name="batdongsan",
            source_id="test_bds_comp_01",
            title="Bán căn hộ Vinhome Smart City",
            company_name="Vinhomes",
            primary_phone="0912345678",
            price=2500000000.0,
            area=65.0,
            address="Quận Nam Từ Liêm, Hà Nội",
            city="Hà Nội",
            raw_data={"description": "Căn hộ cao cấp đầy đủ tiện ích"},
        )

        icp = ICPCriteria(
            target_locations=["Hà Nội"],
            target_keywords=["smart city", "vinhomes"],
            negative_keywords=["cho thuê"],
        )

        result: CompositeConfidenceResult = ConfidenceGate.evaluate_composite(
            lead,
            icp_criteria=icp,
            intent_tags=["smart city"],
        )

        assert isinstance(result, CompositeConfidenceResult)
        assert result.schema_completeness_score == 1.0  # Phone, Price, District, Area, Title all present
        assert result.icp_fit_score > 80.0
        assert result.intent_signal_score >= 70.0
        # 0.4 * 100 + 0.4 * icp_fit + 0.2 * intent_signal
        expected_score = round(0.4 * 100.0 + 0.4 * result.icp_fit_score + 0.2 * result.intent_signal_score, 2)
        assert result.confidence_score == pytest.approx(expected_score, rel=1e-2)
        assert lead.confidence_score == result.confidence_score
        assert lead.icp_fit_score == result.icp_fit_score
        assert lead.intent_signal_score == result.intent_signal_score

    def test_composite_confidence_negative_keyword_rejection(self) -> None:
        """Lead containing negative keywords should receive 0.0 ICP fit score."""
        lead = NormalizedLead(
            source_name="chotot",
            source_id="test_ct_comp_02",
            title="Cho thuê văn phòng trọn gói",
            company_name="Văn phòng ABC",
            primary_phone="0987654321",
            price=15000000.0,
            address="Quận Cầu Giấy, Hà Nội",
            city="Hà Nội",
            raw_data={"description": "Cho thuê mặt bằng kinh doanh"},
        )

        icp = ICPCriteria(
            target_locations=["Hà Nội"],
            negative_keywords=["cho thuê"],
        )

        result = ConfidenceGate.evaluate_composite(lead, icp_criteria=icp)
        assert result.icp_fit_score == 0.0
        assert result.confidence_score < 50.0

    @pytest.mark.asyncio
    async def test_orchestrator_execute_multi_source_with_campaign_spec(self) -> None:
        """LeadGenOrchestrator should execute search from CampaignSpec and pre-filter raw records."""
        orchestrator = LeadGenOrchestrator()

        spec = CampaignSpec(
            name="IT Hiring in HCMC",
            workspace_id=42,
            signal_triggers=["hiring"],
            target_sources=["vn_jobs"],
            icp_criteria=ICPCriteria(
                target_locations=["Hồ Chí Minh"],
                target_keywords=["Python", "FastAPI"],
                negative_keywords=["Java"],
            ),
            max_total_leads=10,
        )

        raw_match = RawLeadRecord(
            source_name="vn_jobs",
            source_id="job_01",
            data={
                "title": "Senior Python Developer",
                "company_name": "Tech Corp",
                "location": "Hồ Chí Minh",
                "phone": "0901234567",
                "description": "Looking for FastAPI and Python experts",
            },
        )
        raw_negative = RawLeadRecord(
            source_name="vn_jobs",
            source_id="job_02",
            data={
                "title": "Senior Java Developer",
                "company_name": "Legacy Corp",
                "location": "Hồ Chí Minh",
                "phone": "0909998887",
                "description": "Java Spring Boot developer required",
            },
        )

        from unittest.mock import MagicMock
        mock_adapter = MagicMock()
        mock_adapter.source_name = "vn_jobs"
        mock_adapter.category = LeadSourceCategory.JOB_MARKET
        mock_adapter.last_execution_status = "ok"
        mock_adapter.search_leads = AsyncMock(return_value=[raw_match, raw_negative])
        mock_adapter.normalize_lead.side_effect = lambda raw: NormalizedLead(
            source_name=raw.source_name,
            source_id=raw.source_id,
            title=raw.data.get("title"),
            company_name=raw.data.get("company_name"),
            city=raw.data.get("location"),
            primary_phone=raw.data.get("phone"),
            address=raw.data.get("location"),
            price=20000000,
            area=50,
            raw_data=raw.data,
        )

        with patch.object(orchestrator.registry, "resolve_adapters_for_campaign", return_value=[mock_adapter]):
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=42,
                campaign_spec=spec,
            )

            assert isinstance(result, LeadGenOrchestratorResult)
            assert result.status == "completed"
            # raw_negative should have been pre-filtered before normalize
            assert len(result.leads) == 1
            assert result.leads[0].source_id == "job_01"
            assert result.leads[0].icp_fit_score is not None
            assert result.leads[0].icp_fit_score > 70.0

    @pytest.mark.asyncio
    async def test_orchestrator_execute_and_persist_with_campaign_spec(
        self,
        db_session: AsyncSession,
        db_workspace: Workspace,
        db_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LeadGenOrchestrator.execute_and_persist should work end-to-end with CampaignSpec and DB."""
        from app.config import config
        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key-campaign-very-secure-32chars")
        from app.db import Lead, VerifiedContact

        orchestrator = LeadGenOrchestrator()
        table_uuid = uuid4()
        ws_table = WorkspaceTable(
            id=table_uuid,
            workspace_id=db_workspace.id,
            name="Campaign Generated Table",
        )
        db_session.add(ws_table)
        await db_session.flush()

        spec = CampaignSpec(
            name="Real Estate Investor Outreach",
            workspace_id=db_workspace.id,
            table_id=str(table_uuid),
            client_id=None,
            signal_triggers=["real_estate"],
            target_sources=["batdongsan"],
            icp_criteria=ICPCriteria(
                target_locations=["Hà Nội"],
                target_keywords=["mặt phố"],
            ),
            max_total_leads=5,
        )

        mock_normalized_lead = NormalizedLead(
            source_name="batdongsan",
            source_id="bds_camp_pers_01",
            title="Bán nhà mặt phố Hoàn Kiếm",
            company_name="Bất Động Sản Hoàn Kiếm",
            canonical_domain="bds-hoankiem.vn",
            primary_phone="0919887766",
            primary_email="contact@bds-hoankiem.vn",
            contact_name="Lê Văn C",
            price=25000000000,
            city="Hà Nội",
            address="Hoàn Kiếm, Hà Nội",
            area=80.0,
            confidence_score=92.5,
            sources=["batdongsan"],
            raw_data={"url": "https://batdongsan.com.vn/tin-bds-01"},
        )

        mock_search_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=1,
            total_deduplicated=1,
            leads=[mock_normalized_lead],
            degraded_sources=[],
            table_id=str(table_uuid),
        )

        with patch.object(orchestrator, "execute_multi_source_lead_gen", AsyncMock(return_value=mock_search_result)):
            res = await orchestrator.execute_and_persist(
                session=db_session,
                workspace_id=db_workspace.id,
                campaign_spec=spec,
            )

            assert res.status == "completed"
            assert len(res.leads) == 1

            stmt = select(Lead).where(
                Lead.workspace_id == db_workspace.id,
                Lead.table_id == table_uuid,
            )
            saved_lead = (await db_session.execute(stmt)).scalar_one_or_none()
            assert saved_lead is not None
            assert saved_lead.company_name == "Bất Động Sản Hoàn Kiếm"
            assert saved_lead.fit_score == 92.5
            assert saved_lead.table_id == table_uuid

            contact_stmt = select(VerifiedContact).where(
                VerifiedContact.workspace_id == db_workspace.id,
            )
            contacts = (await db_session.execute(contact_stmt)).scalars().all()
            from app.services.pii.verified_contact_encryption import (
                VerifiedContactEncryption,
            )
            cipher = VerifiedContactEncryption()
            phones = [cipher.decrypt(c.phone) for c in contacts if c.phone]
            assert "0919887766" in phones
