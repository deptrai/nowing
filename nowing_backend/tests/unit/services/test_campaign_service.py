"""Unit tests cho campaign_service (Epic 44.1).

AsyncMock session — không DB thật. Cover: concurrent guard, opt-in gating,
fail-open savepoint junction, finalize trạng thái, enum values.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.enums import (
    CampaignRunStatus,
    CampaignSource,
    CampaignStatus,
    CampaignTrigger,
)
from app.lead_intelligence.services import campaign_service
from app.lead_intelligence.services.campaign_service import (
    ConcurrentCampaignRunError,
    campaign_to_response,
    finalize_campaign_run,
    get_or_create_campaign,
    open_campaign_run,
    persist_campaign_leads,
)

pytestmark = pytest.mark.unit


def _campaign(direction: str = "demand") -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.workspace_id = 1
    c.direction = direction
    return c


def _full_campaign(**over) -> MagicMock:
    """Campaign mock đủ scalar fields mapper đọc (45.1)."""
    c = _campaign(direction=over.get("direction", "demand"))
    c.name = "Camp"
    c.status = "draft"
    c.input_payload = over.get("input_payload")
    c.source = over.get("source", "created")
    c.next_run_at = over.get("next_run_at")
    c.schedule_frequency = over.get("schedule_frequency")
    c.schedule_cron = over.get("schedule_cron")
    c.max_runs = over.get("max_runs")
    c.skipped_by_quota = over.get("skipped_by_quota", 0)
    c.created_by = uuid.uuid4()
    c.created_at = datetime.now(timezone.utc)
    return c


def _mapper_session(latest_row: tuple | None, collected: int) -> AsyncMock:
    """Session trả lần lượt: latest run row → count leads junction."""
    run_res = MagicMock()
    run_res.first.return_value = latest_row
    count_res = MagicMock()
    count_res.scalar_one.return_value = collected
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[run_res, count_res])
    return session


# ---------------------------------------------------------------------------
# Enums — khớp FE campaignStatusSchema 1:1
# ---------------------------------------------------------------------------


class TestEnums:
    def test_campaign_status_matches_fe_schema(self) -> None:
        assert {s.value for s in CampaignStatus} == {
            "draft",
            "scheduled",
            "running",
            "paused",
            "completed",
            "failed",
            "archived",
        }

    def test_run_status_values(self) -> None:
        assert {s.value for s in CampaignRunStatus} == {
            "queued",
            "running",
            "succeeded",
            "failed",
        }

    def test_trigger_values(self) -> None:
        assert {t.value for t in CampaignTrigger} == {
            "manual",
            "scheduled",
            "api",
        }

    def test_source_values(self) -> None:
        assert {s.value for s in CampaignSource} == {
            "created",
            "execute",
            "api",
        }


# ---------------------------------------------------------------------------
# open_campaign_run — concurrent guard
# ---------------------------------------------------------------------------


class TestOpenCampaignRun:
    @pytest.mark.asyncio
    async def test_raises_when_running_run_exists(self) -> None:
        session = AsyncMock()
        existing_id = uuid.uuid4()
        # execute() → advisory lock + select running; result.first() trả row
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=(existing_id,)))
        )
        campaign = _campaign()
        with patch.object(
            campaign_service, "session", create=True
        ):
            with patch(
                "app.lead_intelligence.services.campaign_service.session",
                create=True,
            ):
                # session.get trả campaign sau advisory lock
                async def _get(model, key):
                    return campaign

                session.get = AsyncMock(side_effect=_get)
                with pytest.raises(ConcurrentCampaignRunError):
                    await open_campaign_run(
                        campaign.id,
                        CampaignTrigger.API.value,
                        session,
                    )

    @pytest.mark.asyncio
    async def test_acquires_advisory_lock_before_check(self) -> None:
        """Lock phải được execute TRƯỚC khi select running run."""
        session = AsyncMock()
        # 44.3: execute được gọi thêm 2 lần cho quota counts — cùng mock
        # trả first()=None (không run 'running') + scalar_one()=0 (dưới quota).
        session.execute = AsyncMock(
            return_value=MagicMock(
                first=MagicMock(return_value=None),
                scalar_one=MagicMock(return_value=0),
            )
        )
        campaign = _campaign()
        session.get = AsyncMock(return_value=campaign)
        session.add = MagicMock()
        session.flush = AsyncMock()

        await open_campaign_run(
            campaign.id, CampaignTrigger.MANUAL.value, session
        )

        first_sql = str(session.execute.call_args_list[0].args[0])
        assert "pg_advisory_xact_lock" in first_sql
        assert "hashtext" in first_sql

    @pytest.mark.asyncio
    async def test_run_created_running_with_snapshot(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                first=MagicMock(return_value=None),
                scalar_one=MagicMock(return_value=0),
            )
        )
        campaign = _campaign()
        session.get = AsyncMock(return_value=campaign)
        session.add = MagicMock()
        session.flush = AsyncMock()

        snapshot = {"name": "Test", "direction": "demand"}
        run = await open_campaign_run(
            campaign.id,
            CampaignTrigger.API.value,
            session,
            spec_snapshot=snapshot,
        )
        assert run.status == CampaignRunStatus.RUNNING.value
        assert run.trigger == CampaignTrigger.API.value
        assert run.spec_snapshot == snapshot
        assert run.campaign_id == campaign.id
        # campaign bị đánh dấu running trong lúc chạy
        assert campaign.status == CampaignStatus.RUNNING.value
        session.add.assert_called_once()


# ---------------------------------------------------------------------------
# get_or_create_campaign
# ---------------------------------------------------------------------------


class TestGetOrCreateCampaign:
    @pytest.mark.asyncio
    async def test_insert_uses_on_conflict_workspace_name_direction(self) -> None:
        session = AsyncMock()
        new_id = uuid.uuid4()
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=(new_id,)))
        )
        campaign = _campaign()
        campaign.id = new_id
        session.get = AsyncMock(return_value=campaign)

        result = await get_or_create_campaign(
            session,
            workspace_id=1,
            name="Chiến dịch A",
            direction="demand",
            source=CampaignSource.EXECUTE.value,
        )
        stmt = str(session.execute.call_args_list[0].args[0])
        assert "on conflict (workspace_id, name, direction) do nothing" in stmt.lower()
        assert result.id == new_id

    @pytest.mark.asyncio
    async def test_reselect_when_conflict(self) -> None:
        """Row mất do insert đồng thời → re-SELECT."""
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )
        existing = _campaign()
        scalars = MagicMock()
        scalars.scalar_one.return_value = existing
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=None)),
                scalars,
            ]
        )
        result = await get_or_create_campaign(
            session,
            workspace_id=1,
            name="X",
            direction="supply",
        )
        assert result is existing


# ---------------------------------------------------------------------------
# persist_campaign_leads — fail-open savepoint
# ---------------------------------------------------------------------------


class TestPersistCampaignLeads:
    @pytest.mark.asyncio
    async def test_fail_open_on_junction_error(self) -> None:
        campaign = _campaign()
        run_id = uuid.uuid4()
        stats: dict = {}

        class _Savepoint:
            async def __aenter__(self):
                raise RuntimeError("junction insert exploded")

            async def __aexit__(self, *args):
                return None

        session = MagicMock()
        session.begin_nested = MagicMock(return_value=_Savepoint())

        # Không raise — fail-open
        await persist_campaign_leads(
            session,
            campaign=campaign,
            run_id=run_id,
            accepted_lead_ids=[uuid.uuid4(), uuid.uuid4()],
            role="buyer",
            stats=stats,
        )
        assert stats.get("junction_failed") is True

    @pytest.mark.asyncio
    async def test_empty_ids_no_savepoint(self) -> None:
        session = MagicMock()
        session.begin_nested = MagicMock()
        stats: dict = {}
        await persist_campaign_leads(
            session,
            campaign=_campaign(),
            run_id=uuid.uuid4(),
            accepted_lead_ids=[],
            role="buyer",
            stats=stats,
        )
        session.begin_nested.assert_not_called()
        assert "junction_failed" not in stats

    @pytest.mark.asyncio
    async def test_success_uses_savepoint(self) -> None:
        campaign = _campaign()
        run_id = uuid.uuid4()
        entered = []

        class _Savepoint:
            async def __aenter__(self):
                entered.append(True)

            async def __aexit__(self, *args):
                return None

        session = MagicMock()
        session.begin_nested = MagicMock(return_value=_Savepoint())
        session.execute = AsyncMock()

        stats: dict = {}
        await persist_campaign_leads(
            session,
            campaign=campaign,
            run_id=run_id,
            accepted_lead_ids=[uuid.uuid4()],
            role="supplier",
            stats=stats,
        )
        assert entered == [True]
        assert "junction_failed" not in stats
        # execute được gọi với pg_insert statement
        stmt = str(session.execute.call_args.args[0])
        assert "campaign_leads" in stmt


# ---------------------------------------------------------------------------
# finalize_campaign_run
# ---------------------------------------------------------------------------


class TestFinalizeCampaignRun:
    @pytest.mark.asyncio
    async def test_succeeded_updates_run_and_campaign(self) -> None:
        run_id = uuid.uuid4()
        campaign_id = uuid.uuid4()
        run = MagicMock()
        run.campaign_id = campaign_id
        session = AsyncMock()
        session.get = AsyncMock(return_value=run)
        # Epic 44.4: execute lần 1 = cost sum (scalar_one), lần 2 = update run,
        # lần 3 = update campaign.
        sum_result = MagicMock()
        sum_result.scalar_one.return_value = 0
        session.execute = AsyncMock(return_value=sum_result)

        await finalize_campaign_run(
            session, run_id=run_id, status="succeeded", stats={"a": 1}
        )
        # 3 execute: cost sum + update run + update campaign
        assert session.execute.await_count == 3
        assert "token_usage" in str(session.execute.call_args_list[0].args[0])
        stmt = str(session.execute.call_args_list[1].args[0])
        assert "campaign_runs" in stmt
        stmt2 = str(session.execute.call_args_list[2].args[0])
        assert "lead_campaigns" in stmt2

    @pytest.mark.asyncio
    async def test_failed_maps_to_failed_campaign(self) -> None:
        run_id = uuid.uuid4()
        run = MagicMock()
        run.campaign_id = uuid.uuid4()
        session = AsyncMock()
        session.get = AsyncMock(return_value=run)
        sum_result = MagicMock()
        sum_result.scalar_one.return_value = 0
        session.execute = AsyncMock(return_value=sum_result)

        await finalize_campaign_run(
            session,
            run_id=run_id,
            status="failed",
            error="x" * 3000,  # bị truncate ở 2000
        )
        values = session.execute.call_args_list[1].args[0].compile().params
        assert values["status"] == "failed"
        assert len(values["error"]) == 2000

    @pytest.mark.asyncio
    async def test_missing_run_still_no_crash(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        sum_result = MagicMock()
        sum_result.scalar_one.return_value = 0
        session.execute = AsyncMock(return_value=sum_result)
        await finalize_campaign_run(
            session, run_id=uuid.uuid4(), status="failed"
        )
        # cost sum + update run, không update campaign
        assert session.execute.await_count == 2


# ---------------------------------------------------------------------------
# campaign_to_response — wire reconcile 45.1
# ---------------------------------------------------------------------------


class TestCampaignToResponse:
    """Mapper expose direction/source/schedule_*/supply_criteria/last_run_at."""

    @pytest.mark.asyncio
    async def test_scalar_fields_and_supply_from_payload(self) -> None:
        now = datetime.now(timezone.utc)
        campaign = _full_campaign(
            input_payload={
                "icp_config": {},
                "source_budget_config": {"sources": ["muasamcong"]},
                "launch_config": {},
                "supply_criteria": {
                    "categories": ["steel"],
                    "locations": ["HCM"],
                },
            },
            next_run_at=now,
            schedule_frequency="daily",
            max_runs=5,
            skipped_by_quota=2,
        )
        session = _mapper_session(latest_row=({"x": 1}, now), collected=7)

        body = await campaign_to_response(session, campaign)

        assert body["direction"] == "demand"
        assert body["source"] == "created"
        assert body["next_run_at"] == now.isoformat()
        assert body["schedule_frequency"] == "daily"
        assert body["schedule_cron"] is None
        assert body["max_runs"] == 5
        assert body["skipped_by_quota"] == 2
        # input_payload thắng snapshot fallback.
        assert body["supply_criteria"] == {
            "categories": ["steel"],
            "locations": ["HCM"],
        }
        assert body["last_run_at"] == now.isoformat()
        assert body["collected_leads_count"] == 7

    @pytest.mark.asyncio
    async def test_supply_fallback_to_snapshot(self) -> None:
        """MAPPER_SUPPLY — supply + payload thiếu supply_criteria → lấy từ
        spec_snapshot run mới nhất."""
        snapshot = {
            "supply_criteria": {"categories": ["steel"], "locations": ["HCM"]}
        }
        campaign = _full_campaign(
            direction="supply",
            source="execute",
            input_payload={
                "icp_config": {},
                "source_budget_config": {"sources": ["websets"]},
            },
        )
        session = _mapper_session(latest_row=(snapshot, None), collected=0)

        body = await campaign_to_response(session, campaign)

        assert body["direction"] == "supply"
        assert body["source"] == "execute"
        assert body["supply_criteria"] == {
            "categories": ["steel"],
            "locations": ["HCM"],
        }
        assert body["last_run_at"] is None
        assert body["skipped_by_quota"] == 0

    @pytest.mark.asyncio
    async def test_supply_missing_everywhere_is_none(self) -> None:
        """Supply campaign nhưng cả payload lẫn snapshot đều thiếu → None."""
        campaign = _full_campaign(
            direction="supply",
            input_payload={"source_budget_config": {"sources": ["websets"]}},
        )
        session = _mapper_session(latest_row=({}, None), collected=0)

        body = await campaign_to_response(session, campaign)
        assert body["supply_criteria"] is None

    @pytest.mark.asyncio
    async def test_demand_no_supply_fallback(self) -> None:
        """Demand campaign KHÔNG fallback snapshot cho supply_criteria."""
        campaign = _full_campaign(
            direction="demand",
            input_payload={"source_budget_config": {"sources": ["websets"]}},
        )
        snapshot = {"supply_criteria": {"categories": ["steel"]}}
        session = _mapper_session(latest_row=(snapshot, None), collected=0)

        body = await campaign_to_response(session, campaign)
        assert body["supply_criteria"] is None

    @pytest.mark.asyncio
    async def test_no_runs_nullable_fields(self) -> None:
        """Campaign chưa chạy: next_run_at/last_run_at None, skipped=0."""
        campaign = _full_campaign(input_payload={})
        session = _mapper_session(latest_row=None, collected=0)

        body = await campaign_to_response(session, campaign)
        assert body["last_run_at"] is None
        assert body["next_run_at"] is None
        assert body["skipped_by_quota"] == 0
        # sources min-1 vẫn đảm bảo.
        assert body["source_budget_config"]["sources"] == ["muasamcong"]
