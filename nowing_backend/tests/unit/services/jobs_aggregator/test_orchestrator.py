"""Smoke tests for the job aggregator orchestrator."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.capabilities.core.types import Capability, CapabilityContext
from app.services.jobs_aggregator import aggregate_jobs
from app.services.jobs_aggregator.schemas import (
    VnJobAggregateInput,
    VnJobAggregateOutput,
)

pytestmark = pytest.mark.unit


def _make_capability(name: str, items: list[dict[str, Any]]) -> Capability:
    from pydantic import BaseModel

    class _In(BaseModel):
        keyword: str

    class _Out(BaseModel):
        items: list[dict[str, Any]]
        cost_micros: int = 0
        degraded: bool = False
        degradation_reason: str | None = None

    async def _exec(input: _In) -> _Out:
        return _Out(items=items, cost_micros=len(items) * 3500)

    return Capability(
        name=name,
        description=name,
        input_schema=_In,
        output_schema=_Out,
        executor=_exec,
        billing_unit=None,
    )


async def test_aggregate_jobs_fan_out_and_dedupe(monkeypatch):
    """Aggregator calls multiple sources, normalizes, deduplicates, and scores."""
    captured: list[tuple[str, dict[str, Any]]] = []

    async def fake_call_source(source: str, payload: dict[str, Any], ctx: CapabilityContext) -> dict[str, Any]:
        captured.append((source, payload))
        if source == "vietnamworks":
            return {
                "items": [
                    {
                        "id": "vw:1",
                        "title": "Senior Data Engineer",
                        "company": "ACB",
                        "location": "Hà Nội",
                        "salary_raw": "Từ 30 triệu",
                        "salary_min": 30000000,
                        "salary_max": 0,
                        "salary_currency": "VND",
                        "salary_period_id": 2,
                        "posted_at": "2026-08-05",
                        "employment_type": "full_time",
                    },
                ],
                "cost_micros": 3500,
                "degraded": False,
            }
        return {"items": [], "degraded": True, "degradation_reason": f"{source}: tos_pending"}

    monkeypatch.setattr("app.services.jobs_aggregator.orchestrator._call_source", fake_call_source)

    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(VnJobAggregateInput(keyword="data engineer", sources=["vietnamworks", "topcv"]), ctx)

    assert isinstance(result, VnJobAggregateOutput)
    assert len(result.items) == 1
    assert result.items[0].title == "Senior Data Engineer"
    assert result.items[0].source == "vietnamworks"
    assert result.degraded is True
    assert any("topcv" in reason for reason in result.degradation_reasons)
    assert result.cost_micros == 3500


async def test_aggregate_jobs_missing_capability(monkeypatch):
    """Missing source capabilities are recorded as degraded."""

    async def fake_call_source(source: str, payload: dict[str, Any], ctx: CapabilityContext) -> dict[str, Any]:
        return {"items": [], "degraded": True, "degradation_reason": f"{source}: capability_not_found"}

    monkeypatch.setattr("app.services.jobs_aggregator.orchestrator._call_source", fake_call_source)

    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(VnJobAggregateInput(keyword="data engineer", sources=["itviec"]), ctx)

    assert result.degraded is True
    assert len(result.items) == 0
