"""Unit tests Epic 44.4 — cost finalize trên ``campaign_runs.cost_micros``.

``_sum_run_cost_micros`` + ``finalize_campaign_run`` ghi tổng
``token_usage.cost_micros`` của các row tagged ``campaign_run_id``. 0 rows →
0 (không NULL); failed run cũng sum. AsyncMock session — không DB thật.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.lead_intelligence.services import campaign_service
from app.lead_intelligence.services.campaign_service import (
    _sum_run_cost_micros,
    finalize_campaign_run,
)

pytestmark = pytest.mark.unit


def _session_with_sum(total: int) -> AsyncMock:
    """Session mock mà mọi execute trả scalar ``total`` từ scalar_one()."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = total
    session.execute = AsyncMock(return_value=result)
    return session


def _run_stub(campaign_id=None) -> MagicMock:
    run = MagicMock()
    run.campaign_id = campaign_id
    return run


class TestSumRunCostMicros:
    @pytest.mark.asyncio
    async def test_zero_rows_returns_zero_not_none(self) -> None:
        """Scrape-only run / 0 usage → COALESCE sum = 0."""
        session = _session_with_sum(0)
        total = await _sum_run_cost_micros(session, uuid.uuid4())
        assert total == 0

    @pytest.mark.asyncio
    async def test_sums_tagged_rows(self) -> None:
        session = _session_with_sum(42_000)
        total = await _sum_run_cost_micros(session, uuid.uuid4())
        assert total == 42_000

    @pytest.mark.asyncio
    async def test_query_filters_jsonb_campaign_run_id(self) -> None:
        run_id = uuid.uuid4()
        session = _session_with_sum(0)
        await _sum_run_cost_micros(session, run_id)
        stmt = session.execute.call_args.args[0]
        params = stmt.compile().params
        assert str(run_id) in params.values()
        assert "token_usage" in str(stmt)

    @pytest.mark.asyncio
    async def test_sum_coalesce_never_null(self) -> None:
        """SQL có COALESCE → NULL sum không bao giờ thành NULL."""
        session = _session_with_sum(0)
        await _sum_run_cost_micros(session, uuid.uuid4())
        stmt = str(session.execute.call_args.args[0]).lower()
        assert "coalesce" in stmt


class TestFinalizeWritesCostMicros:
    @pytest.mark.asyncio
    async def test_succeeded_writes_cost_micros(self) -> None:
        run_id = uuid.uuid4()
        session = _session_with_sum(999)
        session.get = AsyncMock(return_value=_run_stub())

        await finalize_campaign_run(session, run_id=run_id, status="succeeded")

        update_stmt = session.execute.call_args_list[1].args[0]
        values = update_stmt.compile().params
        assert values["cost_micros"] == 999

    @pytest.mark.asyncio
    async def test_failed_run_also_writes_cost_micros(self) -> None:
        """FAILED_RUN_COST: usage đã phát sinh không mất khi run failed."""
        run_id = uuid.uuid4()
        session = _session_with_sum(500)
        session.get = AsyncMock(return_value=_run_stub())

        await finalize_campaign_run(session, run_id=run_id, status="failed")

        values = session.execute.call_args_list[1].args[0].compile().params
        assert values["cost_micros"] == 500
        assert values["status"] == "failed"

    @pytest.mark.asyncio
    async def test_zero_usage_run_writes_zero_not_null(self) -> None:
        run_id = uuid.uuid4()
        session = _session_with_sum(0)
        session.get = AsyncMock(return_value=_run_stub())

        await finalize_campaign_run(session, run_id=run_id, status="succeeded")

        values = session.execute.call_args_list[1].args[0].compile().params
        assert values["cost_micros"] == 0
