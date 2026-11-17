"""Unit tests for supply post-filter tại persist seam (Story 43.3).

Governed by spec: spec-43-3-supply-post-filter-persist-seam.md
I/O matrix: TAX_DROP, TAX_KEEP, RATING_DROP/KEEP/NONE, VERIFIED_STRICT/OK,
SPARSE_DROP, OUTSIDE_LOC, DEMAND_UNTOUCHED, COUNTERS_VIZ.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.campaign.schemas import CampaignSpec, SupplyCriteria
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
    _apply_supply_post_filter,
)

pytestmark = pytest.mark.unit


def _lead(**overrides: Any) -> NormalizedLead:
    """Lead mặc định: company_name + tax_id + city Khánh Hòa (match mặc định)."""
    defaults: dict[str, Any] = {
        "source_name": "enterprise",
        "source_id": "ent_1",
        "company_name": "Công ty A",
        "tax_id": "1234567890",
        "city": "Khánh Hòa",
        "address": "Nha Trang, Khánh Hòa",
        "verified": True,
    }
    defaults.update(overrides)
    return NormalizedLead(**defaults)


def _criteria(**overrides: Any) -> SupplyCriteria:
    """SupplyCriteria mặc định: locations Khánh Hòa, các guard còn lại bật."""
    payload: dict[str, Any] = {
        "categories": ["thiết bị"],
        "locations": ["Khánh Hòa"],
        "require_tax_id": True,
        "min_rating": 0.0,
        "require_verified": False,
    }
    payload.update(overrides)
    return SupplyCriteria(**payload)


def _supply_spec(**criteria_overrides: Any) -> CampaignSpec:
    return CampaignSpec(
        name="supply test",
        workspace_id=1,
        direction="supply",
        supply_criteria=_criteria(**criteria_overrides),
    )


class TestTaxIdGuard:
    def test_tax_drop_no_tax_id(self) -> None:
        """TAX_DROP: lead không tax_id bị drop, counter += 1."""
        leads = [_lead(tax_id=None), _lead()]
        kept, counters = _apply_supply_post_filter(leads, _criteria())
        assert [l.company_name for l in kept] == ["Công ty A"]
        assert counters["filtered_no_tax_id"] == 1

    def test_tax_keep(self) -> None:
        """TAX_KEEP: lead có tax_id giữ nguyên."""
        kept, counters = _apply_supply_post_filter([_lead()], _criteria())
        assert len(kept) == 1
        assert counters["filtered_no_tax_id"] == 0

    def test_tax_guard_off(self) -> None:
        """require_tax_id=False -> lead không tax_id vẫn giữ."""
        kept, _ = _apply_supply_post_filter(
            [_lead(tax_id=None)], _criteria(require_tax_id=False)
        )
        assert len(kept) == 1


class TestMinRatingGuard:
    def test_rating_drop_below(self) -> None:
        """RATING_DROP: rating 3.0 < min 4.0 -> drop."""
        kept, counters = _apply_supply_post_filter(
            [_lead(rating=3.0)], _criteria(min_rating=4.0)
        )
        assert kept == []
        assert counters["filtered_min_rating"] == 1

    def test_rating_keep_above(self) -> None:
        """RATING_KEEP: rating 4.5 >= min 4.0 -> keep."""
        kept, counters = _apply_supply_post_filter(
            [_lead(rating=4.5)], _criteria(min_rating=4.0)
        )
        assert len(kept) == 1
        assert counters["filtered_min_rating"] == 0

    def test_rating_none_kept(self) -> None:
        """RATING_NONE: rating=None giữ (fail-open D3), unrated_kept += 1."""
        kept, counters = _apply_supply_post_filter(
            [_lead(rating=None)], _criteria(min_rating=4.0)
        )
        assert len(kept) == 1
        assert counters["unrated_kept"] == 1
        assert counters["filtered_min_rating"] == 0

    def test_rating_zero_no_filter(self) -> None:
        """min_rating=0 -> không filter rating, rating thấp vẫn giữ."""
        kept, counters = _apply_supply_post_filter(
            [_lead(rating=1.0)], _criteria(min_rating=0.0)
        )
        assert len(kept) == 1
        assert counters["filtered_min_rating"] == 0


class TestVerifiedGuard:
    def test_verified_strict_none_dropped(self) -> None:
        """VERIFIED_STRICT: verified=None -> drop (strict D2)."""
        kept, counters = _apply_supply_post_filter(
            [_lead(verified=None)], _criteria(require_verified=True)
        )
        assert kept == []
        assert counters["filtered_unverified"] == 1

    def test_verified_false_dropped(self) -> None:
        """VERIFIED_STRICT: verified=False -> drop."""
        kept, counters = _apply_supply_post_filter(
            [_lead(verified=False)], _criteria(require_verified=True)
        )
        assert kept == []
        assert counters["filtered_unverified"] == 1

    def test_verified_true_kept(self) -> None:
        """VERIFIED_OK: verified=True -> keep."""
        kept, counters = _apply_supply_post_filter(
            [_lead(verified=True)], _criteria(require_verified=True)
        )
        assert len(kept) == 1
        assert counters["filtered_unverified"] == 0


class TestSparseIdentityGuard:
    def test_sparse_drop(self) -> None:
        """SPARSE_DROP: thiếu cả company_name lẫn tax_id -> drop."""
        kept, counters = _apply_supply_post_filter(
            [_lead(company_name=None, tax_id=None)], _criteria(require_tax_id=False)
        )
        assert kept == []
        assert counters["filtered_sparse_identity"] == 1

    def test_company_name_only_kept(self) -> None:
        """Có company_name, không tax_id (require_tax_id=False) -> keep."""
        kept, counters = _apply_supply_post_filter(
            [_lead(tax_id=None)], _criteria(require_tax_id=False)
        )
        assert len(kept) == 1
        assert counters["filtered_sparse_identity"] == 0

    def test_blank_company_name_dropped(self) -> None:
        """company_name whitespace -> coi như thiếu -> sparse drop."""
        kept, counters = _apply_supply_post_filter(
            [_lead(company_name="   ", tax_id=None)], _criteria(require_tax_id=False)
        )
        assert kept == []
        assert counters["filtered_sparse_identity"] == 1


class TestOutsideLocationsGuard:
    def test_outside_city_dropped(self) -> None:
        """OUTSIDE_LOC: city không match locations -> drop."""
        kept, counters = _apply_supply_post_filter(
            [_lead(city="Hà Nội", address="Cầu Giấy, Hà Nội")], _criteria()
        )
        assert kept == []
        assert counters["filtered_outside_locations"] == 1

    def test_inside_kept(self) -> None:
        """city Khánh Hòa match -> keep."""
        kept, counters = _apply_supply_post_filter([_lead()], _criteria())
        assert len(kept) == 1
        assert counters["filtered_outside_locations"] == 0

    def test_no_city_no_address_dropped(self) -> None:
        """Thiếu cả city lẫn address -> text rỗng -> drop."""
        kept, counters = _apply_supply_post_filter(
            [_lead(city=None, address=None)], _criteria()
        )
        assert kept == []
        assert counters["filtered_outside_locations"] == 1

    def test_nationwide_disables_guard(self) -> None:
        """locations 'toàn quốc' -> bỏ guard location."""
        kept, counters = _apply_supply_post_filter(
            [_lead(city=None, address=None)],
            _criteria(locations=["toàn quốc"]),
        )
        assert len(kept) == 1
        assert counters["filtered_outside_locations"] == 0


class TestDemandUntouched:
    def test_demand_no_filter_no_counters(self) -> None:
        """DEMAND_UNTOUCHED: demand path không filter, counters rỗng mặc định."""
        spec = CampaignSpec(name="demand test", workspace_id=1)
        result = LeadGenOrchestratorResult(
            status="completed",
            leads=[_lead(tax_id=None, company_name=None)],
        )
        # Demand: seam chỉ chạy khi direction == 'supply' — assert trực tiếp điều kiện.
        assert spec.direction == "demand"
        assert spec.supply_criteria is None
        # Result mặc định counters rỗng (không chạy filter).
        assert result.supply_filter_counters == {}


class TestEnterpriseAdapterVerified:
    def test_masothue_record_verified_true(self) -> None:
        """Bản ghi masothue có tax_code -> verified=True."""
        from app.lead_intelligence.adapters.base import RawLeadRecord
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )

        adapter = EnterpriseProcurementLeadAdapter()
        record = RawLeadRecord(
            source_name="enterprise",
            source_id="mst_1",
            data={"company_name": "Công ty B", "tax_code": "9876543210"},
        )
        lead = adapter.normalize_lead(record)
        assert lead.verified is True

    def test_procurement_record_not_verified(self) -> None:
        """Hồ sơ đấu thầu không tax_code/tax_id -> verified=False."""
        from app.lead_intelligence.adapters.base import RawLeadRecord
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )

        adapter = EnterpriseProcurementLeadAdapter()
        record = RawLeadRecord(
            source_name="enterprise",
            source_id="bid_1",
            data={"procurement_bid": "Gói thầu X"},
        )
        lead = adapter.normalize_lead(record)
        assert lead.verified is False


def _savepoint_session() -> MagicMock:
    """Session mock: begin_nested() trả async CM, commit() awaitable."""
    sp = MagicMock()
    sp.__aenter__ = AsyncMock(return_value=None)
    sp.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.begin_nested = MagicMock(return_value=sp)
    session.commit = AsyncMock()
    return session


class TestExecuteAndPersistSeam:
    """COUNTERS_VIZ + seam integration: filter chạy đúng chỗ trong execute_and_persist."""

    def _setup_ingest(self, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
        ingest_mock = AsyncMock(
            return_value={
                "ingested_count": 0,
                "skipped_blacklisted_count": 0,
                "failed_count": 0,
                "execution_time_ms": 1.0,
                "lead_ids": [],
                "lead_id_mapping": {},
                "accepted": [],
                "accepted_lead_ids": [],
            }
        )
        fake_service_instance = MagicMock(ingest_batch=ingest_mock)
        monkeypatch.setattr(
            "app.services.lead_batch_service.LeadBatchService",
            MagicMock(return_value=fake_service_instance),
        )
        return ingest_mock

    @pytest.mark.asyncio
    async def test_supply_run_filters_and_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Supply run: lead no-tax-id bị drop trước ingest_batch, counter visible."""
        ingest_mock = self._setup_ingest(monkeypatch)
        search_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=2,
            total_deduplicated=2,
            leads=[_lead(), _lead(tax_id=None)],
        )
        orchestrator = LeadGenOrchestrator()
        monkeypatch.setattr(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(return_value=search_result),
        )
        monkeypatch.setattr(orchestrator, "_assign_new_leads", AsyncMock())

        result = await orchestrator.execute_and_persist(
            session=_savepoint_session(),
            workspace_id=1,
            query="thiết bị",
            campaign_spec=_supply_spec(),
        )

        assert result.supply_filter_counters["filtered_no_tax_id"] == 1
        assert len(result.leads) == 1
        # ingest_batch chỉ nhận lead đã qua filter.
        assert len(ingest_mock.call_args[0][2]) == 1

    @pytest.mark.asyncio
    async def test_supply_all_dropped_returns_early(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Supply run drop hết -> return sớm, không gọi ingest_batch."""
        ingest_mock = self._setup_ingest(monkeypatch)
        search_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=1,
            total_deduplicated=1,
            leads=[_lead(tax_id=None)],
        )
        orchestrator = LeadGenOrchestrator()
        monkeypatch.setattr(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(return_value=search_result),
        )
        monkeypatch.setattr(orchestrator, "_assign_new_leads", AsyncMock())

        result = await orchestrator.execute_and_persist(
            session=_savepoint_session(),
            workspace_id=1,
            query="thiết bị",
            campaign_spec=_supply_spec(),
        )

        assert result.supply_filter_counters["filtered_no_tax_id"] == 1
        assert result.leads == []
        ingest_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_demand_run_no_filter_no_counters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Demand run: mọi lead đi thẳng ingest_batch, counters rỗng (bit-for-bit)."""
        ingest_mock = self._setup_ingest(monkeypatch)
        leads = [_lead(tax_id=None, company_name=None), _lead()]
        search_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=2,
            total_deduplicated=2,
            leads=leads,
        )
        orchestrator = LeadGenOrchestrator()
        monkeypatch.setattr(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(return_value=search_result),
        )
        monkeypatch.setattr(orchestrator, "_assign_new_leads", AsyncMock())

        spec = CampaignSpec(name="demand test", workspace_id=1)
        result = await orchestrator.execute_and_persist(
            session=_savepoint_session(),
            workspace_id=1,
            query="anything",
            campaign_spec=spec,
        )

        assert result.supply_filter_counters == {}
        # Demand: cả 2 lead (kể cả sparse) đều tới ingest_batch.
        assert len(ingest_mock.call_args[0][2]) == 2
        assert result.leads == leads

    @pytest.mark.asyncio
    async def test_supply_counters_survive_persistence_meta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COUNTERS_VIZ: counters vẫn trong result sau khi persist merge summary."""
        self._setup_ingest(
            monkeypatch
        )  # noqa: F841 — patch LeadBatchService cho seam
        accepted_id = uuid4()
        ingest_mock = AsyncMock(
            return_value={
                "ingested_count": 1,
                "skipped_blacklisted_count": 0,
                "failed_count": 0,
                "execution_time_ms": 1.0,
                "lead_ids": [accepted_id],
                "lead_id_mapping": {},
                "accepted": [True],
                "accepted_lead_ids": [accepted_id],
            }
        )
        monkeypatch.setattr(
            "app.services.lead_batch_service.LeadBatchService",
            MagicMock(return_value=MagicMock(ingest_batch=ingest_mock)),
        )
        search_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=3,
            total_deduplicated=3,
            leads=[
                _lead(),
                _lead(source_id="2", rating=2.0),
                _lead(source_id="3", verified=False),
            ],
        )
        orchestrator = LeadGenOrchestrator()
        monkeypatch.setattr(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(return_value=search_result),
        )
        monkeypatch.setattr(orchestrator, "_assign_new_leads", AsyncMock())

        result = await orchestrator.execute_and_persist(
            session=_savepoint_session(),
            workspace_id=1,
            query="thiết bị",
            campaign_spec=_supply_spec(min_rating=4.0, require_verified=True),
        )

        assert result.supply_filter_counters == {
            "filtered_no_tax_id": 0,
            "filtered_min_rating": 1,
            "filtered_unverified": 1,
            "filtered_sparse_identity": 0,
            "filtered_outside_locations": 0,
            # D3 fail-open: 2 lead unrated (rating=None) được giữ khi min_rating=4.0.
            "unrated_kept": 2,
        }
        assert len(result.leads) == 1
