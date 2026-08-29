"""Unit tests for LeadSourceAdapterRegistry dynamic discovery, category indexing, and intent routing (Story 21.15 / Story 21.20)."""

from __future__ import annotations

from typing import Any

import pytest

from app.lead_intelligence.adapters.base import (
    LeadIntent,
    LeadSourceCategory,
    NormalizedLead,
)
from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
from app.lead_intelligence.adapters.enterprise import (
    EnterpriseProcurementLeadAdapter,
)
from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.adapters.social import SocialLeadAdapter
from app.lead_intelligence.adapters.telegram import TelegramLeadAdapter
from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter
from app.lead_intelligence.services.lead_gen_orchestrator import (
    _post_filter_leads,
)

pytestmark = pytest.mark.unit


class TestLeadSourceAdapterRegistry:
    """Validate dynamic discovery, category indexing, and intent routing."""

    def test_registry_registration_and_retrieval(self) -> None:
        """Should register concrete adapters and retrieve them by source_name."""
        registry = LeadSourceAdapterRegistry()
        bds_adapter = BatdongsanLeadAdapter()
        chotot_adapter = ChototLeadAdapter()

        registry.register(bds_adapter)
        registry.register(chotot_adapter)

        assert registry.get("batdongsan") is bds_adapter
        assert registry.get("chotot") is chotot_adapter
        assert len(registry.list_all()) == 2

    def test_registry_filter_by_category(self) -> None:
        """Should filter registered adapters by LeadSourceCategory."""
        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(JobMarketLeadAdapter())
        registry.register(EnterpriseProcurementLeadAdapter())

        real_estate_adapters = registry.find_by_category(LeadSourceCategory.REAL_ESTATE)
        assert len(real_estate_adapters) == 1
        assert real_estate_adapters[0].source_name == "batdongsan"

        job_adapters = registry.find_by_category(LeadSourceCategory.JOB_MARKET)
        assert len(job_adapters) == 1
        assert job_adapters[0].source_name == "job_market"

    def test_registry_resolve_adapters_for_intent(self) -> None:
        """Should route user intent keywords to relevant adapters."""
        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(ChototLeadAdapter())
        registry.register(MuabanBdsLeadAdapter())
        registry.register(JobMarketLeadAdapter())
        registry.register(VnJobsLeadAdapter())
        registry.register(VietnamWorksLeadAdapter())
        registry.register(EnterpriseProcurementLeadAdapter())
        registry.register(MuaSamCongLeadAdapter())
        registry.register(SocialLeadAdapter())
        registry.register(TelegramLeadAdapter())

        def names(matched: list[Any]) -> set[str]:
            return {a.source_name for a in matched}

        # Intent: Real estate & property — BĐS keywords
        bds_matched = registry.resolve_adapters_for_intent(
            "Tìm nhà đất chung cư biệt thự Hà Nội"
        )
        assert names(bds_matched) == {"batdongsan", "chotot", "muaban_bds"}
        for a in bds_matched:
            assert a.category == LeadSourceCategory.REAL_ESTATE

        # Intent: location + price with no BĐS keyword should default to REAL_ESTATE
        price_location_matched = registry.resolve_adapters_for_intent(
            "quận 7 TP.HCM giá dưới 8 tỷ"
        )
        assert names(price_location_matched) == {"batdongsan", "chotot", "muaban_bds"}

        # Intent: job recruitment (priority order may pick vn_jobs first)
        jobs_matched = registry.resolve_adapters_for_intent(
            "Tìm công ty IT đang tuyển dụng Golang Developer"
        )
        assert all(a.category == LeadSourceCategory.JOB_MARKET for a in jobs_matched)
        assert len(jobs_matched) == 1

        # Intent: procurement
        proc_matched = registry.resolve_adapters_for_intent("gói thầu xây dựng TP.HCM")
        assert names(proc_matched) == {"muasamcong"}

        # Intent: enterprise tax
        ent_matched = registry.resolve_adapters_for_intent("mã số thuế 0123456789")
        assert names(ent_matched) == {"enterprise"}

        # Intent: broker with BĐS keyword must not route to social
        broker_matched = registry.resolve_adapters_for_intent(
            "môi giới bất động sản quận 7"
        )
        assert names(broker_matched) == {"batdongsan", "chotot", "muaban_bds"}

        # Intent: broad query with no signal falls back to all adapters
        fallback_matched = registry.resolve_adapters_for_intent(
            "cho tôi thông tin"
        )
        assert len(fallback_matched) == 10

    def test_registry_resolve_adapters_for_intent_with_lead_intent(self) -> None:
        """Should route seller intent to social first, then BĐS fallback."""
        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(ChototLeadAdapter())
        registry.register(MuabanBdsLeadAdapter())
        registry.register(SocialLeadAdapter())

        def names(matched: list[Any]) -> set[str]:
            return {a.source_name for a in matched}

        # Seller intent should prefer social (buyer-demand) adapters.
        sell_matched = registry.resolve_adapters_for_intent(
            "Tôi cần bán 10 lô đất ký gửi quận 7",
            intent=LeadIntent.SELL,
        )
        assert "social" in names(sell_matched)

        # Buyer intent should still route to BĐS listings.
        buy_matched = registry.resolve_adapters_for_intent(
            "Tìm 10 nhà bán quận 7 TP.HCM giá dưới 8 tỷ",
            intent=LeadIntent.BUY,
        )
        assert names(buy_matched) == {"batdongsan", "chotot", "muaban_bds"}

        # Neutral / missing intent must remain backward-compatible.
        neutral_matched = registry.resolve_adapters_for_intent(
            "quận 7 TP.HCM giá dưới 8 tỷ"
        )
        assert names(neutral_matched) == {"batdongsan", "chotot", "muaban_bds"}

    def test_registry_raises_key_error_for_unknown_adapter(self) -> None:
        """Should raise KeyError when requesting non-existent adapter."""
        registry = LeadSourceAdapterRegistry()
        with pytest.raises(KeyError):
            registry.get("unknown_source")


class TestRegistryIntentRoutingStory2120:
    """Validate 21.20 source routing and deduplication."""

    def test_resolve_job_intent_deduplicates_to_vn_jobs(self) -> None:
        """Generic job query should route to VnJobs, not all job adapters."""
        registry = LeadSourceAdapterRegistry()
        registry.register(BatdongsanLeadAdapter())
        registry.register(ChototLeadAdapter())
        registry.register(MuabanBdsLeadAdapter())
        registry.register(JobMarketLeadAdapter())
        registry.register(VnJobsLeadAdapter())
        registry.register(VietnamWorksLeadAdapter())
        registry.register(EnterpriseProcurementLeadAdapter())
        registry.register(MuaSamCongLeadAdapter())
        registry.register(SocialLeadAdapter())

        matched = registry.resolve_adapters_for_intent(
            "công ty AI tuyển dụng Senior Python tại Hà Nội"
        )
        names = {a.source_name for a in matched}
        assert "vn_jobs" in names
        assert "batdongsan" not in names
        assert "chotot" not in names
        assert "muaban_bds" not in names
        assert "muasamcong" not in names
        assert "enterprise" not in names
        assert "vietnamworks" not in names

    def test_resolve_explicit_vietnamworks(self) -> None:
        """Explicit VietnamWorks keyword should route to VietnamWorks adapter."""
        registry = LeadSourceAdapterRegistry()
        registry.register(JobMarketLeadAdapter())
        registry.register(VnJobsLeadAdapter())
        registry.register(VietnamWorksLeadAdapter())

        matched = registry.resolve_adapters_for_intent(
            "tìm việc Python trên VietnamWorks"
        )
        names = {a.source_name for a in matched}
        assert "vietnamworks" in names
        assert "vn_jobs" not in names
        assert "job_market" not in names

    def test_resolve_procurement_intent_does_not_trigger_enterprise(self) -> None:
        """Procurement query should route to muasamcong, not the tax directory."""
        registry = LeadSourceAdapterRegistry()
        registry.register(EnterpriseProcurementLeadAdapter())
        registry.register(MuaSamCongLeadAdapter())

        matched = registry.resolve_adapters_for_intent(
            "gói thầu phần mềm CRM tại Hà Nội"
        )
        names = {a.source_name for a in matched}
        assert "muasamcong" in names
        assert "enterprise" not in names


class TestLeadGenPostFilter:
    """LeadGenOrchestrator post-filter should drop price and location outliers."""

    def test_post_filter_drops_price_and_location_outliers(self) -> None:
        """Should drop leads with price above max or in wrong location."""
        leads = [
            NormalizedLead(
                source_name="batdongsan",
                source_id="1",
                title="Nhà quận 7",
                price=7_000_000_000,
                city="Hồ Chí Minh",
            ),
            NormalizedLead(
                source_name="batdongsan",
                source_id="2",
                title="Nhà quận 7",
                price=9_000_000_000,
                city="Hồ Chí Minh",
            ),
            NormalizedLead(
                source_name="batdongsan",
                source_id="3",
                title="Nhà quận 7",
                price=6_000_000_000,
                city="Hà Nội",
            ),
        ]
        filtered = _post_filter_leads(
            leads,
            query="nhà quận 7 TP.HCM giá dưới 8 tỷ",
            filters={"locations": ["TP.HCM"]},
        )
        assert len(filtered) == 1
        assert filtered[0].source_id == "1"
