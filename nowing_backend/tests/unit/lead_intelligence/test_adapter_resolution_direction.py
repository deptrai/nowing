"""Story 43.2 — Direction-aware adapter resolution tests.

Matrix từ spec: supply fail-closed, deterministic ordering, wrapper propagate,
target_sources thắng, dict spec, query synthesis 2 seam, ICP pre-filter no-op,
demand bit-for-bit (snapshot trước khi thêm nhánh supply).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    LeadSourceCategory,
    RawLeadRecord,
)
from app.lead_intelligence.adapters.registry import LeadSourceAdapterRegistry
from app.lead_intelligence.campaign.schemas import (
    CampaignSpec,
    ICPCriteria,
    SupplyCriteria,
)

pytestmark = pytest.mark.unit

SUPPLY_ADAPTERS = {"enterprise", "muasamcong"}
DEMAND_ADAPTERS = {
    "batdongsan",
    "chotot",
    "muaban_bds",
    "job_market",
    "vn_jobs",
    "vietnamworks",
    "social",
    "telegram",
    "shopee",
    "tiktok_shop",
    "news",
    "websets",
}


def _supply_spec(**overrides) -> CampaignSpec:
    """Supply spec mẫu: categories không khớp tên adapter nào -> fallback all."""
    payload: dict = {
        "name": "Supply Campaign",
        "workspace_id": 1,
        "direction": "supply",
        "supply_criteria": SupplyCriteria(
            categories=["thiết bị y tế"], locations=["Hà Nội"]
        ),
    }
    payload.update(overrides)
    return CampaignSpec(**payload)


def _demand_re_spec() -> CampaignSpec:
    """Demand spec khớp REAL_ESTATE + keyword bđs (snapshot: 3 adapter bds)."""
    return CampaignSpec(
        name="Demand RE",
        workspace_id=1,
        icp_criteria=ICPCriteria(
            target_categories=[LeadSourceCategory.REAL_ESTATE],
            target_keywords=["bất động sản"],
            target_locations=["Hà Nội"],
        ),
    )


# Demand snapshot — thứ tự resolve TRƯỚC khi thêm nhánh supply (captured 2026-11-17,
# baseline c456623df): resolve_adapters_for_spec + resolve_adapters_for_campaign
# đều trả đúng thứ tự này, campaign mutate priority 10/9/8 + quota 100/90/80.
DEMAND_RE_ORDER = ["batdongsan", "chotot", "muaban_bds"]
DEMAND_RE_PRIORITY = [("batdongsan", 10, 100), ("chotot", 9, 90), ("muaban_bds", 8, 80)]
DEMAND_EMPTY_ORDER = [
    "batdongsan",
    "chotot",
    "muaban_bds",
    "job_market",
    "vn_jobs",
    "vietnamworks",
    "enterprise",
    "muasamcong",
    "social",
    "telegram",
    "shopee",
    "tiktok_shop",
    "news",
    "websets",
]


class TestSupplyResolution:
    """Supply branch: fail-closed, chỉ supply_eligible."""

    def setup_method(self) -> None:
        self.registry = LeadSourceAdapterRegistry.get_default()

    def test_supply_eligible_flag_on_adapters(self) -> None:
        """T1: enterprise + muasamcong supply_eligible=True, còn lại False."""
        flagged = {
            a.source_name
            for a in self.registry.list_all()
            if getattr(a, "supply_eligible", False)
        }
        assert flagged == SUPPLY_ADAPTERS

    def test_supply_match_single_adapter_not_fallback(self) -> None:
        """SUPPLY_MATCH thật: 'muasamcong' khớp đúng 1 adapter — phân biệt
        được nhánh match vs fallback (fallback trả cả 2)."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(categories=["muasamcong"], locations=["HN"])
        )
        names = [a.source_name for a in self.registry.resolve_adapters_for_spec(spec)]
        assert names == ["muasamcong"]

    def test_supply_match_shared_keyword_returns_both(self) -> None:
        """Keyword 'enterprise' có trong cả 2 haystack -> match trả cả hai."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(categories=["enterprise"], locations=["HN"])
        )
        names = [a.source_name for a in self.registry.resolve_adapters_for_spec(spec)]
        assert set(names) == SUPPLY_ADAPTERS

    def test_supply_match_case_and_diacritics_insensitive(self) -> None:
        """Keyword viết hoa / không dấu vẫn match (nhất quán demand path)."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(categories=["MuaSamCong"], locations=["HN"])
        )
        names = [a.source_name for a in self.registry.resolve_adapters_for_spec(spec)]
        assert names == ["muasamcong"]

    def test_supply_no_match_fails_closed_to_all_supply(self) -> None:
        """SUPPLY_NO_MATCH: categories lạ -> trả TẤT CẢ supply_eligible, không demand."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(
                categories=["xyz-lạ- completely"], locations=["HN"]
            )
        )
        result = self.registry.resolve_adapters_for_spec(spec)
        names = [a.source_name for a in result]
        assert set(names) == SUPPLY_ADAPTERS
        assert not (set(names) & DEMAND_ADAPTERS)

    def test_supply_fail_closed_never_returns_demand_adapter(self) -> None:
        """SUPPLY_FAIL_CLOSED: bất kỳ input supply nào cũng 0 demand adapter."""
        specs = [
            _supply_spec(),
            _supply_spec(
                supply_criteria=SupplyCriteria(
                    categories=["bất động sản", "tuyển dụng"], locations=["SG"]
                )
            ),
        ]
        for spec in specs:
            names = {a.source_name for a in self.registry.resolve_adapters_for_spec(spec)}
            assert names <= SUPPLY_ADAPTERS
            assert not (names & DEMAND_ADAPTERS)

    def test_supply_ordering_deterministic_registration_order(self) -> None:
        """SUPPLY_DETERMINISTIC: 2 lần resolve cùng kết quả, theo thứ tự đăng ký."""
        spec = _supply_spec()
        first = [a.source_name for a in self.registry.resolve_adapters_for_spec(spec)]
        second = [a.source_name for a in self.registry.resolve_adapters_for_spec(spec)]
        registration_order = [
            a.source_name
            for a in self.registry.list_all()
            if getattr(a, "supply_eligible", False)
        ]
        assert first == second == registration_order

    def test_supply_does_not_mutate_priority_or_quota(self) -> None:
        """Supply không mutate priority/lead_quota trên shared adapter instances."""
        spec = _supply_spec()
        before = {
            a.source_name: (a.priority, a.lead_quota)
            for a in self.registry.list_all()
        }
        self.registry.resolve_adapters_for_campaign(spec)
        after = {
            a.source_name: (a.priority, a.lead_quota)
            for a in self.registry.list_all()
        }
        assert before == after


class TestSupplyWrapperPropagation:
    """T3: resolve_adapters_for_campaign propagate direction."""

    def setup_method(self) -> None:
        self.registry = LeadSourceAdapterRegistry.get_default()

    def test_wrapper_supply_returns_supply_eligible_only(self) -> None:
        """WRAPPER_SUPPLY: không rơi xuống category→intent→list_all demand chain."""
        adapters, location_fallback = self.registry.resolve_adapters_for_campaign(
            _supply_spec()
        )
        names = {a.source_name for a in adapters}
        assert names == SUPPLY_ADAPTERS
        assert not (names & DEMAND_ADAPTERS)
        assert location_fallback is False

    def test_wrapper_supply_no_demand_fallback_chain(self) -> None:
        """Supply + không match gì vẫn KHÔNG gọi resolve_adapters_for_intent/list_all."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(
                categories=["không-tồn-tại"], locations=["Điện Biên"]
            )
        )
        with (
            patch.object(
                self.registry,
                "resolve_adapters_for_intent",
                side_effect=AssertionError("supply không được rơi vào intent routing"),
            ),
            patch.object(
                self.registry,
                "list_all",
                side_effect=AssertionError("supply không được rơi vào list_all"),
            ),
        ):
            adapters, _ = self.registry.resolve_adapters_for_campaign(spec)
            assert {a.source_name for a in adapters} == SUPPLY_ADAPTERS


class TestTargetSourcesWins:
    """target_sources explicit thắng cả 2 direction."""

    def setup_method(self) -> None:
        self.registry = LeadSourceAdapterRegistry.get_default()

    def test_target_sources_wins_supply(self) -> None:
        """TARGET_SRC_WINS: supply + target_sources=['chotot'] -> chotot (demand adapter)."""
        spec = _supply_spec(target_sources=["chotot"])
        result = self.registry.resolve_adapters_for_spec(spec)
        assert [a.source_name for a in result] == ["chotot"]

    def test_target_sources_wins_demand(self) -> None:
        """Demand + target_sources vẫn giữ behavior cũ."""
        spec = CampaignSpec(
            name="d", workspace_id=1, target_sources=["shopee", "news"]
        )
        result = self.registry.resolve_adapters_for_spec(spec)
        assert [a.source_name for a in result] == ["shopee", "news"]


class TestDictSpecDirection:
    """D3 + DICT_SPEC: direction đọc đúng qua helper khi spec là dict."""

    def setup_method(self) -> None:
        self.registry = LeadSourceAdapterRegistry.get_default()

    def test_dict_spec_supply_resolves_supply(self) -> None:
        spec: dict = {
            "name": "dict supply",
            "workspace_id": 1,
            "direction": "supply",
            "supply_criteria": {
                "categories": ["thầu"],
                "locations": ["HN"],
            },
        }
        names = {a.source_name for a in self.registry.resolve_adapters_for_spec(spec)}
        assert names <= SUPPLY_ADAPTERS
        assert not (names & DEMAND_ADAPTERS)

    def test_dict_spec_supply_wrapper_propagates(self) -> None:
        spec: dict = {
            "name": "dict supply",
            "workspace_id": 1,
            "direction": "supply",
            "supply_criteria": {
                "categories": ["không-tồn-tại"],
                "locations": ["HN"],
            },
        }
        adapters, _ = self.registry.resolve_adapters_for_campaign(spec)
        assert {a.source_name for a in adapters} == SUPPLY_ADAPTERS

    def test_dict_spec_demand_resolves_demand(self) -> None:
        spec: dict = {"name": "dict demand", "workspace_id": 1}
        names = {a.source_name for a in self.registry.resolve_adapters_for_spec(spec)}
        # Demand dict rỗng -> list_all fallback (behavior cũ)
        assert names == DEMAND_ADAPTERS | SUPPLY_ADAPTERS


class TestQuerySynthesis:
    """T4: supply + query rỗng -> synthesize từ categories + locations ở 2 seam."""

    def setup_method(self) -> None:
        from app.lead_intelligence.campaign.planner import LeadGenPlanner

        self.planner = LeadGenPlanner()

    def test_planner_supply_synthesizes_query(self) -> None:
        """QUERY_PREFLIGHT: planner seam."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(
                categories=["thiết bị y tế", "vật tư"], locations=["Hà Nội", "HCM"]
            )
        )
        query = self.planner._build_query_for_adapter(spec, LeadSourceCategory.ENTERPRISE)
        assert query == "thiết bị y tế vật tư Hà Nội HCM"

    def test_planner_supply_base_query_still_wins(self) -> None:
        spec = _supply_spec(query="từ khóa gốc")
        query = self.planner._build_query_for_adapter(spec, LeadSourceCategory.ENTERPRISE)
        assert query == "từ khóa gốc"

    def test_planner_supply_no_icp_read(self) -> None:
        """Supply query synthesis không đọc icp_criteria (giả lập supply có ICP)."""
        spec = _supply_spec(
            supply_criteria=SupplyCriteria(categories=["x"], locations=["y"]),
        )
        # Supply spec bị validator 43.1 cấm non-default icp_criteria — pin behavior:
        # nếu tương lai nới lỏng, query synthesis vẫn KHÔNG được đọc icp_criteria.
        object.__setattr__(
            spec,
            "icp_criteria",
            ICPCriteria(target_keywords=["kw-icp"], target_industries=["ind-icp"]),
        )
        query = self.planner._build_query_for_adapter(spec, LeadSourceCategory.ENTERPRISE)
        assert "kw-icp" not in query
        assert "ind-icp" not in query

    @pytest.mark.asyncio
    async def test_orchestrator_supply_synthesizes_effective_query(self) -> None:
        """QUERY_EXECUTE: orchestrator seam — route /run truyền query=''."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orch = LeadGenOrchestrator()
        captured_queries: list[str] = []

        async def fake_search(workspace_id, query, filters=None, limit=50):
            captured_queries.append(query)
            return []

        adapter = MagicMock(source_name="enterprise")
        adapter.search_leads = AsyncMock(side_effect=fake_search)
        adapter.normalize_lead = MagicMock(return_value=None)
        adapter.extract_contact_candidates = MagicMock(return_value=[])

        spec = _supply_spec(
            supply_criteria=SupplyCriteria(
                categories=["thiết bị y tế"], locations=["Hà Nội"]
            )
        )
        with patch.object(
            orch.registry,
            "resolve_adapters_for_campaign",
            return_value=([adapter], False),
        ):
            result = await orch.execute_multi_source_lead_gen(
                workspace_id=1, query="", campaign_spec=spec
            )
        assert captured_queries == ["thiết bị y tế Hà Nội"]
        assert result.status in ("completed", "partial")

    @pytest.mark.asyncio
    async def test_orchestrator_demand_query_unchanged(self) -> None:
        """Demand: query rỗng + không supply -> giữ behavior cũ (query='')."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orch = LeadGenOrchestrator()
        captured_queries: list[str] = []

        async def fake_search(workspace_id, query, filters=None, limit=50):
            captured_queries.append(query)
            return []

        adapter = MagicMock(source_name="batdongsan")
        adapter.search_leads = AsyncMock(side_effect=fake_search)
        adapter.normalize_lead = MagicMock(return_value=None)
        adapter.extract_contact_candidates = MagicMock(return_value=[])

        spec = CampaignSpec(name="d", workspace_id=1, query="từ khóa demand")
        with patch.object(
            orch.registry,
            "resolve_adapters_for_campaign",
            return_value=([adapter], False),
        ):
            await orch.execute_multi_source_lead_gen(
                workspace_id=1, query="", campaign_spec=spec
            )
        assert captured_queries == ["từ khóa demand"]


class TestICPPrefilterNoOp:
    """T5 + ICP_PREFILTER_NOOP: pre_filter_by_icp không chạy khi supply."""

    @pytest.mark.asyncio
    async def test_supply_skips_icp_prefilter(self) -> None:
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orch = LeadGenOrchestrator()
        prefilter_calls: list[str] = []

        def spy_prefilter(cls, raw_record, icp_criteria=None, location_profile=None):
            # autospec trên classmethod: tham số đầu (cls) thực tế là RawLeadRecord,
            # tham số thứ hai (raw_record) thực tế là ICPCriteria.
            prefilter_calls.append(cls.source_id)
            return False, 0.0

        async def fake_search(workspace_id, query, filters=None, limit=50):
            return [
                RawLeadRecord(
                    source_name="enterprise",
                    source_id="r1",
                    data={"title": "Công ty ABC"},
                )
            ]

        adapter = MagicMock(source_name="enterprise")
        adapter.search_leads = AsyncMock(side_effect=fake_search)
        adapter.normalize_lead = MagicMock(return_value=None)
        adapter.extract_contact_candidates = MagicMock(return_value=[])

        spec = _supply_spec()
        with (
            patch.object(
                orch.registry,
                "resolve_adapters_for_campaign",
                return_value=([adapter], False),
            ),
            patch.object(
                LeadGenOrchestrator,
                "pre_filter_by_icp",
                autospec=True,
                side_effect=lambda cls, raw_record, icp=None, location_profile=None: spy_prefilter(
                    cls, raw_record, icp, location_profile
                ),
            ),
        ):
            await orch.execute_multi_source_lead_gen(
                workspace_id=1, query="", campaign_spec=spec
            )
        assert prefilter_calls == []

    @pytest.mark.asyncio
    async def test_demand_still_calls_icp_prefilter(self) -> None:
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orch = LeadGenOrchestrator()
        prefilter_calls: list[str] = []

        def spy_prefilter(cls, raw_record, icp_criteria=None, location_profile=None):
            # autospec trên classmethod: tham số đầu (cls) thực tế là RawLeadRecord,
            # tham số thứ hai (raw_record) thực tế là ICPCriteria.
            prefilter_calls.append(cls.source_id)
            return False, 0.0

        async def fake_search(workspace_id, query, filters=None, limit=50):
            return [
                RawLeadRecord(
                    source_name="batdongsan",
                    source_id="r2",
                    data={"title": "Nhà đất"},
                )
            ]

        adapter = MagicMock(source_name="batdongsan")
        adapter.search_leads = AsyncMock(side_effect=fake_search)
        adapter.normalize_lead = MagicMock(return_value=None)
        adapter.extract_contact_candidates = MagicMock(return_value=[])

        spec = CampaignSpec(name="d", workspace_id=1, query="nhà đất")
        with (
            patch.object(
                orch.registry,
                "resolve_adapters_for_campaign",
                return_value=([adapter], False),
            ),
            patch.object(
                LeadGenOrchestrator,
                "pre_filter_by_icp",
                autospec=True,
                side_effect=lambda cls, raw_record, icp=None, location_profile=None: spy_prefilter(
                    cls, raw_record, icp, location_profile
                ),
            ),
        ):
            await orch.execute_multi_source_lead_gen(
                workspace_id=1, query="", campaign_spec=spec
            )
        assert prefilter_calls == ["r2"]


class TestDemandRegression:
    """Demand path bit-for-bit — pin snapshot trước khi thêm nhánh supply."""

    def setup_method(self) -> None:
        self.registry = LeadSourceAdapterRegistry.get_default()

    def test_demand_re_spec_spec_resolver_order(self) -> None:
        """DEMAND_UNCHANGED: resolve_adapters_for_spec giữ nguyên thứ tự snapshot."""
        result = [a.source_name for a in self.registry.resolve_adapters_for_spec(_demand_re_spec())]
        assert result == DEMAND_RE_ORDER

    def test_demand_re_spec_wrapper_order_and_priority_mutation(self) -> None:
        """Demand wrapper: thứ tự + mutation priority/quota giữ nguyên snapshot."""
        adapters, location_fallback = self.registry.resolve_adapters_for_campaign(
            _demand_re_spec()
        )
        assert [a.source_name for a in adapters] == DEMAND_RE_ORDER
        assert location_fallback is False
        assert [(a.source_name, a.priority, a.lead_quota) for a in adapters] == (
            DEMAND_RE_PRIORITY
        )

    def test_demand_empty_spec_list_all_fallback(self) -> None:
        """Demand spec rỗng -> list_all fallback theo thứ tự đăng ký (snapshot)."""
        adapters, location_fallback = self.registry.resolve_adapters_for_campaign(
            CampaignSpec(name="empty", workspace_id=1)
        )
        assert [a.source_name for a in adapters] == DEMAND_EMPTY_ORDER
        assert location_fallback is False

    def test_demand_job_market_order(self) -> None:
        """Demand keyword tuyển dụng -> job_market dedup order (snapshot SPEC4)."""
        spec = CampaignSpec(
            name="job",
            workspace_id=1,
            icp_criteria=ICPCriteria(
                target_keywords=["tuyển dụng", "nhân sự", "itviec"]
            ),
        )
        result = [a.source_name for a in self.registry.resolve_adapters_for_spec(spec)]
        assert result == ["job_market", "vn_jobs", "vietnamworks"]
