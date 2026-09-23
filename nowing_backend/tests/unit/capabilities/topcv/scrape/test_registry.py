"""The topcv namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    topcv,  # noqa: F401
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.topcv.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_topcv_scrape_is_registered_and_billable():
    cap = get_capability("topcv.scrape")

    assert cap.name == "topcv.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.TOPCV_JOB


class TestTopCVExecutorEscalation:
    """Story 12-2, Item 5: anti-bot escalation un-gated on None run_id / ctx."""

    @pytest.mark.asyncio
    async def test_escalation_triggers_with_fallback_uuid_when_ctx_is_none(
        self, monkeypatch
    ):
        from uuid import UUID

        from app.capabilities.topcv.scrape.executor import build_scrape_executor

        captured_delay: list[dict] = []

        async def _mock_scrape(_params):
            return {
                "items": [],
                "cost_micros": 0,
                "degraded": True,
                "degradation_reason": "bot_detected",
                "total_items": 0,
            }

        monkeypatch.setattr(
            "app.capabilities.topcv.scrape.executor.scrape_topcv",
            _mock_scrape,
        )
        monkeypatch.setattr(
            "app.capabilities.topcv.scrape.executor.capture_platform_anti_bot_screenshot_task.delay",
            lambda **kwargs: captured_delay.append(kwargs),
        )

        executor = build_scrape_executor()
        output = await executor(ScrapeInput(keyword="python"), ctx=None)

        assert output.degraded is True
        assert len(captured_delay) == 1
        call_args = captured_delay[0]
        assert call_args["capability"] == "topcv.scrape"
        assert call_args["domain"] == "topcv.vn"
        assert call_args["block_type"] == "bot_detected"
        assert call_args["workspace_id"] == 0
        # Must be valid UUID string so celery task won't crash on UUID(run_id)
        assert UUID(call_args["run_id"]) is not None

    @pytest.mark.asyncio
    async def test_escalation_uses_ctx_run_id_when_provided(self, monkeypatch):
        from app.capabilities.core.types import CapabilityContext
        from app.capabilities.topcv.scrape.executor import build_scrape_executor

        captured_delay: list[dict] = []

        async def _mock_scrape(_params):
            return {
                "items": [],
                "cost_micros": 0,
                "degraded": True,
                "degradation_reason": "access_blocked",
                "total_items": 0,
            }

        monkeypatch.setattr(
            "app.capabilities.topcv.scrape.executor.scrape_topcv",
            _mock_scrape,
        )
        monkeypatch.setattr(
            "app.capabilities.topcv.scrape.executor.capture_platform_anti_bot_screenshot_task.delay",
            lambda **kwargs: captured_delay.append(kwargs),
        )

        ctx = CapabilityContext(
            session=None,  # type: ignore[arg-type]
            run_id="11111111-2222-3333-4444-555555555555",
            workspace_id=42,
        )
        executor = build_scrape_executor()
        output = await executor(ScrapeInput(keyword="python"), ctx=ctx)

        assert output.degraded is True
        assert len(captured_delay) == 1
        assert captured_delay[0]["run_id"] == "11111111-2222-3333-4444-555555555555"
        assert captured_delay[0]["workspace_id"] == 42
        assert captured_delay[0]["block_type"] == "access_blocked"

    @pytest.mark.asyncio
    async def test_no_escalation_when_not_degraded(self, monkeypatch):
        from app.capabilities.topcv.scrape.executor import build_scrape_executor

        captured_delay: list[dict] = []

        async def _mock_scrape(_params):
            return {
                "items": [{"id": "topcv:1", "title": "Dev"}],
                "cost_micros": 1000,
                "degraded": False,
                "degradation_reason": None,
                "total_items": 1,
            }

        monkeypatch.setattr(
            "app.capabilities.topcv.scrape.executor.scrape_topcv",
            _mock_scrape,
        )
        monkeypatch.setattr(
            "app.capabilities.topcv.scrape.executor.capture_platform_anti_bot_screenshot_task.delay",
            lambda **kwargs: captured_delay.append(kwargs),
        )

        executor = build_scrape_executor()
        output = await executor(ScrapeInput(keyword="python"), ctx=None)

        assert output.degraded is False
        assert len(captured_delay) == 0

