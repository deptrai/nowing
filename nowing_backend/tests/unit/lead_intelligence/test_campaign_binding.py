"""Unit tests cho campaign binding trong lead_gen_orchestrator (Epic 44.1).

Cover: opt-in gating (agent path không truyền campaign → 0 row nhưng vẫn
commit), mọi return path finalize run, role theo direction, junction chỉ dùng
``summary["accepted_lead_ids"]``, result.tagging.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lead_intelligence.adapters.base import NormalizedLead
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
    LeadGenOrchestratorResult,
)

pytestmark = pytest.mark.unit


def _lead() -> NormalizedLead:
    return NormalizedLead(
        source_name="batdongsan",
        source_id="lead-1",
        title="Công ty A",
        company_name="Công ty A",
    )


def _campaign(direction: str = "demand") -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.workspace_id = 1
    c.direction = direction
    return c


def _make_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
    search_leads: list[NormalizedLead] | None = None,
    summary: dict | None = None,
    ingest_error: Exception | None = None,
) -> LeadGenOrchestrator:
    orch = LeadGenOrchestrator()
    search_result = LeadGenOrchestratorResult(
        total_discovered=len(search_leads or []),
        total_deduplicated=len(search_leads or []),
        leads=list(search_leads or []),
    )
    orch.execute_multi_source_lead_gen = AsyncMock(return_value=search_result)

    service = MagicMock()
    if ingest_error is not None:
        service.ingest_batch = AsyncMock(side_effect=ingest_error)
    else:
        service.ingest_batch = AsyncMock(
            return_value=summary
            or {
                "ingested_count": len(search_leads or []),
                "skipped_blacklisted_count": 0,
                "failed_count": 0,
                "execution_time_ms": 12.5,
                "lead_ids": [],
                "lead_id_mapping": {},
                "blocked_hmacs": [],
                "accepted_lead_ids": [],
                "accepted": [],
            }
        )
    # monkeypatch tự revert sau test — KHÔNG dùng patcher.start() (rò rỉ
    # sang test khác trong cùng session, vd. test_lead_stream_buffer).
    monkeypatch.setattr(
        "app.services.lead_batch_service.LeadBatchService",
        MagicMock(return_value=service),
    )
    return orch


@pytest.fixture(autouse=True)
def _no_assign(monkeypatch):
    monkeypatch.setattr(
        LeadGenOrchestrator,
        "_assign_new_leads",
        AsyncMock(return_value=None),
    )


class TestOptInGating:
    @pytest.mark.asyncio
    async def test_agent_path_no_campaign_still_commits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Không truyền campaign → 0 row campaign NHƯNG vẫn commit (fix T0)."""
        orch = _make_orchestrator(monkeypatch, search_leads=[_lead()])
        session = AsyncMock()

        result = await orch.execute_and_persist(
            session=session,
            workspace_id=1,
            campaign_spec=None,
            limit=10,
        )
        session.commit.assert_awaited()
        assert result.campaign_id is None
        assert result.campaign_run_id is None

    @pytest.mark.asyncio
    async def test_no_leads_path_commits_and_finalizes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return path không leads → run 'succeeded' + commit."""
        orch = _make_orchestrator(monkeypatch, search_leads=[])
        session = AsyncMock()
        campaign = _campaign()
        run_id = uuid.uuid4()

        with patch(
            "app.lead_intelligence.services.campaign_service.finalize_campaign_run",
            new=AsyncMock(),
        ) as finalize:
            result = await orch.execute_and_persist(
                session=session,
                workspace_id=1,
                campaign_spec=None,
                limit=10,
                campaign=campaign,
                campaign_run_id=run_id,
            )
        finalize.assert_awaited_once()
        kwargs = finalize.call_args.kwargs
        assert kwargs["status"] == "succeeded"
        assert kwargs["run_id"] == run_id
        session.commit.assert_awaited()
        assert result.campaign_id == campaign.id
        assert result.campaign_run_id == run_id

    @pytest.mark.asyncio
    async def test_ingest_failure_finalizes_failed_and_commits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest exception → run 'failed' + commit (leads roll back trong
        savepoint nhưng outer tx vẫn commit được)."""
        orch = _make_orchestrator(
            monkeypatch,
            search_leads=[_lead()],
            ingest_error=RuntimeError("DB abort"),
        )
        session = AsyncMock()
        campaign = _campaign()
        run_id = uuid.uuid4()

        with patch(
            "app.lead_intelligence.services.campaign_service.finalize_campaign_run",
            new=AsyncMock(),
        ) as finalize:
            result = await orch.execute_and_persist(
                session=session,
                workspace_id=1,
                campaign_spec=None,
                limit=10,
                campaign=campaign,
                campaign_run_id=run_id,
            )
        finalize.assert_awaited_once()
        assert finalize.call_args.kwargs["status"] == "failed"
        session.commit.assert_awaited()
        assert result.status == "degraded"
        assert result.campaign_run_id == run_id

    @pytest.mark.asyncio
    async def test_success_path_persists_junction_with_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Success → junction chỉ từ accepted_lead_ids, role theo direction."""
        lead_id = uuid.uuid4()
        summary = {
            "ingested_count": 1,
            "skipped_blacklisted_count": 0,
            "failed_count": 0,
            "execution_time_ms": 9.0,
            "lead_ids": [lead_id],
            "lead_id_mapping": {},
            "blocked_hmacs": [],
            "accepted_lead_ids": [lead_id],
            "accepted": [True],
        }
        orch = _make_orchestrator(monkeypatch, search_leads=[_lead()], summary=summary)
        # session.begin_nested phải là async CM (AsyncMock trả coroutine).
        session = AsyncMock()
        sp = AsyncMock()
        sp.__aenter__ = AsyncMock(return_value=None)
        sp.__aexit__ = AsyncMock(return_value=None)
        session.begin_nested = MagicMock(return_value=sp)
        campaign = _campaign(direction="supply")
        run_id = uuid.uuid4()

        with (
            patch(
                "app.lead_intelligence.services.campaign_service.persist_campaign_leads",
                new=AsyncMock(),
            ) as persist,
            patch(
                "app.lead_intelligence.services.campaign_service.finalize_campaign_run",
                new=AsyncMock(),
            ) as finalize,
        ):
            result = await orch.execute_and_persist(
                session=session,
                workspace_id=1,
                campaign_spec=None,
                limit=10,
                campaign=campaign,
                campaign_run_id=run_id,
            )
        persist.assert_awaited_once()
        assert persist.call_args.kwargs["accepted_lead_ids"] == [lead_id]
        assert persist.call_args.kwargs["role"] == "supplier"
        finalize.assert_awaited_once()
        assert finalize.call_args.kwargs["status"] == "succeeded"
        session.commit.assert_awaited()
        assert result.campaign_id == campaign.id

    @pytest.mark.asyncio
    async def test_demand_role_is_buyer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        lead_id = uuid.uuid4()
        summary = {
            "ingested_count": 1,
            "skipped_blacklisted_count": 0,
            "failed_count": 0,
            "execution_time_ms": 1.0,
            "lead_ids": [lead_id],
            "lead_id_mapping": {},
            "blocked_hmacs": [],
            "accepted_lead_ids": [lead_id],
            "accepted": [True],
        }
        orch = _make_orchestrator(monkeypatch, search_leads=[_lead()], summary=summary)
        session = AsyncMock()
        sp = AsyncMock()
        sp.__aenter__ = AsyncMock(return_value=None)
        sp.__aexit__ = AsyncMock(return_value=None)
        session.begin_nested = MagicMock(return_value=sp)
        campaign = _campaign(direction="demand")

        with (
            patch(
                "app.lead_intelligence.services.campaign_service.persist_campaign_leads",
                new=AsyncMock(),
            ) as persist,
            patch(
                "app.lead_intelligence.services.campaign_service.finalize_campaign_run",
                new=AsyncMock(),
            ),
        ):
            await orch.execute_and_persist(
                session=session,
                workspace_id=1,
                campaign_spec=None,
                limit=10,
                campaign=campaign,
                campaign_run_id=uuid.uuid4(),
            )
        assert persist.call_args.kwargs["role"] == "buyer"

    @pytest.mark.asyncio
    async def test_never_infers_from_spec_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Chỉ truyền campaign_spec (không campaign) → KHÔNG bookkeeping."""
        from app.lead_intelligence.campaign.schemas import CampaignSpec

        spec = CampaignSpec(name="Tự nhiên có tên", workspace_id=1)
        lead_id = uuid.uuid4()
        summary = {
            "ingested_count": 1,
            "skipped_blacklisted_count": 0,
            "failed_count": 0,
            "execution_time_ms": 1.0,
            "lead_ids": [lead_id],
            "lead_id_mapping": {},
            "blocked_hmacs": [],
            "accepted_lead_ids": [lead_id],
            "accepted": [True],
        }
        orch = _make_orchestrator(monkeypatch, search_leads=[_lead()], summary=summary)
        session = AsyncMock()

        with (
            patch(
                "app.lead_intelligence.services.campaign_service.persist_campaign_leads",
                new=AsyncMock(),
            ) as persist,
            patch(
                "app.lead_intelligence.services.campaign_service.finalize_campaign_run",
                new=AsyncMock(),
            ) as finalize,
        ):
            await orch.execute_and_persist(
                session=session,
                workspace_id=1,
                campaign_spec=spec,
                limit=10,
            )
        persist.assert_not_awaited()
        finalize.assert_not_awaited()
        session.commit.assert_awaited()
