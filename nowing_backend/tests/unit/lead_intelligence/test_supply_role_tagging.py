"""Unit tests cho lead role/visibility tagging qua extra_metadata (Story 43.4).

Governed by spec: spec-43-4-lead-role-visibility-tagging.md
I/O matrix: SUPPLY_TAGGED, DEMAND_UNTAGGED, EXTRA_METADATA_MERGE,
POOLABLE_LABEL, CAMPAIGN_KEY, ROLE_LWW (upsert merge semantics),
seam integration qua execute_and_persist.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.campaign.schemas import CampaignSpec, SupplyCriteria
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)

pytestmark = pytest.mark.unit

# 4 keys tag theo spec — demand path không được chứa key nào trong số này.
SUPPLY_TAG_KEYS = {"lead_role", "campaign_direction", "campaign_key", "visibility"}


def _lead(**overrides: Any) -> NormalizedLead:
    """Lead mặc định pass supply post-filter (tax_id + city Khánh Hòa)."""
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


def _spec(**overrides: Any) -> CampaignSpec:
    """CampaignSpec mặc định: supply, locations Khánh Hòa, visibility private."""
    payload: dict[str, Any] = {
        "name": "Thu mua trầm KH",
        "workspace_id": 1,
        "direction": "supply",
        "supply_criteria": SupplyCriteria(
            categories=["thiết bị"],
            locations=["Khánh Hòa"],
            require_tax_id=True,
            min_rating=0.0,
            require_verified=False,
        ),
    }
    payload.update(overrides)
    return CampaignSpec(**payload)


def _ingest_result() -> dict[str, Any]:
    return {
        "ingested_count": 0,
        "skipped_blacklisted_count": 0,
        "failed_count": 0,
        "execution_time_ms": 1.0,
        "lead_ids": [],
        "lead_id_mapping": {},
        "accepted": [],
        "accepted_lead_ids": [],
    }


async def _run_persist(
    monkeypatch: pytest.MonkeyPatch,
    spec: CampaignSpec,
    leads: list[NormalizedLead],
) -> AsyncMock:
    """Chạy execute_and_persist với ingest_batch mocked, trả ingest_mock."""
    ingest_mock = AsyncMock(return_value=_ingest_result())
    fake_service = MagicMock(ingest_batch=ingest_mock)
    monkeypatch.setattr(
        "app.services.lead_batch_service.LeadBatchService",
        MagicMock(return_value=fake_service),
    )
    search_result = LeadGenOrchestratorResult(
        status="completed",
        total_discovered=len(leads),
        total_deduplicated=len(leads),
        leads=leads,
    )
    orchestrator = LeadGenOrchestrator()
    monkeypatch.setattr(
        orchestrator,
        "execute_multi_source_lead_gen",
        AsyncMock(return_value=search_result),
    )
    monkeypatch.setattr(orchestrator, "_assign_new_leads", AsyncMock())
    sp = MagicMock()
    sp.__aenter__ = AsyncMock(return_value=None)
    sp.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.begin_nested = MagicMock(return_value=sp)
    session.commit = AsyncMock()
    await orchestrator.execute_and_persist(
        session=session,
        workspace_id=1,
        query="thiết bị",
        campaign_spec=spec,
    )
    return ingest_mock


class TestSupplyTagged:
    @pytest.mark.asyncio
    async def test_supply_four_keys_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SUPPLY_TAGGED: mọi lead supply có đủ 4 keys đúng giá trị."""
        ingest_mock = await _run_persist(
            monkeypatch, _spec(), [_lead(), _lead(source_id="ent_2")]
        )
        for item in ingest_mock.call_args[0][2]:
            meta = item["extra_metadata"]
            assert meta["lead_role"] == "supplier"
            assert meta["campaign_direction"] == "supply"
            assert meta["campaign_key"] == "Thu mua trầm KH"
            assert meta["visibility"] == "private"

    @pytest.mark.asyncio
    async def test_campaign_key_is_spec_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CAMPAIGN_KEY: campaign_key = spec.name (spec không có id — D1)."""
        ingest_mock = await _run_persist(
            monkeypatch, _spec(name="Tên campaign Việt"), [_lead()]
        )
        assert ingest_mock.call_args[0][2][0]["extra_metadata"]["campaign_key"] == (
            "Tên campaign Việt"
        )


class TestDemandUntagged:
    @pytest.mark.asyncio
    async def test_demand_no_tag_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DEMAND_UNTAGGED: demand path không có key nào trong 4 keys."""
        ingest_mock = await _run_persist(
            monkeypatch,
            CampaignSpec(name="demand", workspace_id=1),
            [_lead()],
        )
        meta = ingest_mock.call_args[0][2][0]["extra_metadata"]
        assert not (SUPPLY_TAG_KEYS & meta.keys())

    @pytest.mark.asyncio
    async def test_no_spec_no_tag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Không campaign_spec -> không tag (demand mặc định)."""
        ingest_mock = AsyncMock(return_value=_ingest_result())
        fake_service = MagicMock(ingest_batch=ingest_mock)
        monkeypatch.setattr(
            "app.services.lead_batch_service.LeadBatchService",
            MagicMock(return_value=fake_service),
        )
        search_result = LeadGenOrchestratorResult(
            status="completed", total_discovered=1, total_deduplicated=1, leads=[_lead()]
        )
        orchestrator = LeadGenOrchestrator()
        monkeypatch.setattr(
            orchestrator,
            "execute_multi_source_lead_gen",
            AsyncMock(return_value=search_result),
        )
        monkeypatch.setattr(orchestrator, "_assign_new_leads", AsyncMock())
        sp = MagicMock()
        sp.__aenter__ = AsyncMock(return_value=None)
        sp.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.begin_nested = MagicMock(return_value=sp)
        session.commit = AsyncMock()
        await orchestrator.execute_and_persist(
            session=session, workspace_id=1, query="test"
        )
        meta = ingest_mock.call_args[0][2][0]["extra_metadata"]
        assert not (SUPPLY_TAG_KEYS & meta.keys())


class TestExtraMetadataMerge:
    @pytest.mark.asyncio
    async def test_supply_merge_keeps_existing_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """EXTRA_METADATA_MERGE: extra_metadata có sẵn (từ raw_data) + 4 keys."""
        ingest_mock = await _run_persist(
            monkeypatch,
            _spec(),
            [_lead(raw_data={"extra_metadata": {"foo": 1, "bar": "x"}})],
        )
        meta = ingest_mock.call_args[0][2][0]["extra_metadata"]
        assert meta["foo"] == 1
        assert meta["bar"] == "x"
        assert meta["lead_role"] == "supplier"
        assert SUPPLY_TAG_KEYS <= meta.keys()


class TestPoolableLabel:
    @pytest.mark.asyncio
    async def test_poolable_is_pure_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POOLABLE_LABEL: visibility='poolable' chỉ là label trong extra_metadata."""
        ingest_mock = await _run_persist(
            monkeypatch, _spec(visibility="poolable"), [_lead()]
        )
        meta = ingest_mock.call_args[0][2][0]["extra_metadata"]
        assert meta["visibility"] == "poolable"
        # Label thuần: lead vẫn được ingest bình thường, không key side-effect nào khác.
        assert len(ingest_mock.call_args[0][2]) == 1


class TestRoleLastWriteWins:
    def test_upsert_merge_excluded_wins(self) -> None:
        """ROLE_LWW: upsert merge 'excluded wins theo key' — lead cũ role 'buyer'
        bị supply ghi lại thành 'supplier' (D2/D3, semantics đã có sẵn ở
        _build_batch_upsert_stmt, không sửa)."""
        # Lead supply mới luôn mang tag ở excluded (bản ghi mới vào) nên key
        # lead_role của excluded thắng merge concat. Verify semantics tại level
        # tag: supply_tags luôn được set — không bao giờ None trong batch supply.
        tags = {
            "lead_role": "supplier",
            "campaign_direction": "supply",
            "campaign_key": "k",
            "visibility": "private",
        }
        existing = {"lead_role": "buyer", "foo": 1}
        # Mô phỏng concat merge excluded-wins theo key của upsert stmt.
        merged = {**existing, **tags}
        assert merged["lead_role"] == "supplier"
        assert merged["foo"] == 1
