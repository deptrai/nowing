"""ATDD tests for jobs_aggregator orchestrator (AC-1, AC-3).

Covers source fan-out, per-source caps, degradation tracking,
and degraded_source_ids.
"""

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


# ---------------------------------------------------------------------------
# Existing passing tests (keep green)
# ---------------------------------------------------------------------------


async def test_aggregate_jobs_fan_out_and_dedupe(monkeypatch):
    """Aggregator calls multiple sources, normalizes, deduplicates, and scores."""
    captured: list[tuple[str, dict[str, Any]]] = []

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
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
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: tos_pending",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )

    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="data engineer", sources=["vietnamworks", "topcv"]),
        ctx,
    )

    assert isinstance(result, VnJobAggregateOutput)
    assert len(result.items) == 1
    assert result.items[0].title == "Senior Data Engineer"
    assert result.items[0].source == "vietnamworks"
    assert result.degraded is True
    assert "SOURCE_FAILED" in result.degradation_reasons  # canonical enum
    assert "topcv" in result.degraded_source_ids
    assert result.cost_micros == 3500


async def test_aggregate_jobs_missing_capability(monkeypatch):
    """Missing source capabilities are recorded as degraded."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: capability_not_found",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )

    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="data engineer", sources=["itviec"]), ctx
    )

    assert result.degraded is True
    assert len(result.items) == 0


# ===========================================================================
# AC-1: Fan-out to 3 sources with configurable sources list + per-source caps
# ===========================================================================


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


async def test_fan_out_default_sources_all_three(monkeypatch):
    """should call vietnamworks, topcv, itviec when sources is omitted."""
    called: list[str] = []

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        called.append(source)
        return {"items": [], "degraded": False}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    await aggregate_jobs(VnJobAggregateInput(keyword="dev"), ctx)
    assert set(called) == {"vietnamworks", "topcv", "itviec"}


async def test_fan_out_only_listed_sources(monkeypatch):
    """should call only sources in the sources param."""
    called: list[str] = []

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        called.append(source)
        return {"items": [], "degraded": False}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec", "topcv"]), ctx
    )
    assert set(called) == {"itviec", "topcv"}
    assert "vietnamworks" not in called


async def test_fan_out_max_items_per_source_passed(monkeypatch):
    """should pass max_items = max_items_per_source in the source payload."""
    captured_payloads: dict[str, dict] = {}

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        captured_payloads[source] = payload
        return {"items": [], "degraded": False}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", max_items_per_source=50), ctx
    )
    for payload in captured_payloads.values():
        assert payload.get("max_items") == 50


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking
# ---------------------------------------------------------------------------


async def test_fan_out_source_key_error_degraded(monkeypatch):
    """should handle _call_source raising KeyError (capability not found) and mark source as degraded."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        raise KeyError(f"capability {source} not found")

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert result.degraded is True
    assert "itviec" in result.degraded_source_ids


async def test_fan_out_source_exception_degraded(monkeypatch):
    """should handle _call_source raising Exception and mark source as degraded."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        raise RuntimeError("scraper error")

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert result.degraded is True
    assert "itviec" in result.degraded_source_ids


async def test_fan_out_source_returns_none(monkeypatch):
    """should handle _call_source returning None (no items, no degraded flag) and treat as empty source."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return None  # type: ignore[return-value]

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert len(result.items) == 0
    assert "itviec" not in result.degraded_source_ids  # None ≠ degraded


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases
# ---------------------------------------------------------------------------


async def test_fan_out_max_items_zero(monkeypatch):
    """should fetch no items when max_items_per_source=0."""
    captured: list[dict] = []

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        captured.append(payload)
        return {"items": [], "degraded": False}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", max_items_per_source=0), ctx
    )
    assert len(result.items) == 0
    for payload in captured:
        assert payload.get("max_items") == 0


async def test_fan_out_empty_sources_list(monkeypatch):
    """should handle sources=[] without raising and return a valid output."""
    called: list[str] = []

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        called.append(source)
        return {"items": [], "degraded": False}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(VnJobAggregateInput(keyword="dev", sources=[]), ctx)
    assert isinstance(result, VnJobAggregateOutput)
    # Behavior when sources=[] is not specified; we just assert no crash.


# ---------------------------------------------------------------------------
# Pattern 4 — Arithmetic
# ---------------------------------------------------------------------------


async def test_fan_out_cost_micros_sum(monkeypatch):
    """should compute cost_micros as exactly sum(source.cost_micros) across all non-degraded sources."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        if source == "vietnamworks":
            return {
                "items": [{"id": "1", "title": "Dev", "company": "Co"}],
                "cost_micros": 3500,
                "degraded": False,
            }
        if source == "itviec":
            return {
                "items": [{"id": "2", "title": "Dev", "company": "Co"}],
                "cost_micros": 2000,
                "degraded": False,
            }
        return {"items": [], "degraded": True, "degradation_reason": "topcv: failed"}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["vietnamworks", "itviec", "topcv"]),
        ctx,
    )
    # Only non-degraded sources contribute to cost
    assert result.cost_micros == 3500 + 2000


# ===========================================================================
# AC-3: Degradation tracking with canonical enum + degraded_source_ids
# ===========================================================================


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


async def test_degradation_source_ids_set(monkeypatch):
    """should return degraded_source_ids listing failed source names."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        if source == "topcv":
            return {
                "items": [],
                "degraded": True,
                "degradation_reason": "topcv: tos_pending",
            }
        return {
            "items": [{"id": "1", "title": "Dev", "company": "Co"}],
            "degraded": False,
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["vietnamworks", "topcv"]), ctx
    )
    assert result.degraded is True
    assert "topcv" in result.degraded_source_ids
    assert "vietnamworks" not in result.degraded_source_ids


async def test_degradation_reasons_canonical_enum(monkeypatch):
    """should return degradation_reasons with values from enum {SOURCE_FAILED, ANTI_BOT, RATE_LIMIT, PARTIAL_DATA}."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        if source == "topcv":
            return {"items": [], "degraded": True, "degradation_reason": "RATE_LIMIT"}
        return {"items": [], "degraded": True, "degradation_reason": "ANTI_BOT"}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["vietnamworks", "topcv"]), ctx
    )
    for reason in result.degradation_reasons:
        assert reason in ("SOURCE_FAILED", "ANTI_BOT", "RATE_LIMIT", "PARTIAL_DATA")


async def test_degradation_successful_sources_items_returned(monkeypatch):
    """should still normalize and return items from successful sources when some fail."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        if source == "vietnamworks":
            return {
                "items": [{"id": "1", "title": "Dev", "company": "Co"}],
                "degraded": False,
            }
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: failed",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["vietnamworks", "topcv", "itviec"]),
        ctx,
    )
    assert result.degraded is True
    assert len(result.items) == 1
    assert result.items[0].title == "Dev"


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking: raw reason mapping
# ---------------------------------------------------------------------------


async def test_degradation_tos_pending_mapped_to_source_failed(monkeypatch):
    """should map raw reason 'tos_pending' to canonical SOURCE_FAILED."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: tos_pending",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "SOURCE_FAILED" in result.degradation_reasons


async def test_degradation_capability_not_found_mapped(monkeypatch):
    """should map raw reason 'capability_not_found' to canonical SOURCE_FAILED."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: capability_not_found",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "SOURCE_FAILED" in result.degradation_reasons


async def test_degradation_rate_limit_mapped(monkeypatch):
    """should map raw reason '429' or 'rate_limit' to canonical RATE_LIMIT."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {"items": [], "degraded": True, "degradation_reason": "429"}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "RATE_LIMIT" in result.degradation_reasons


async def test_degradation_anti_bot_mapped(monkeypatch):
    """should map raw reason '403' or 'captcha' to canonical ANTI_BOT."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {"items": [], "degraded": True, "degradation_reason": "captcha"}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "ANTI_BOT" in result.degradation_reasons


async def test_degradation_unknown_reason_mapped_to_source_failed(monkeypatch):
    """should map unknown reason string to canonical SOURCE_FAILED."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {"items": [], "degraded": True, "degradation_reason": "something_weird"}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "SOURCE_FAILED" in result.degradation_reasons


async def test_degradation_none_reason_mapped(monkeypatch):
    """should map None reason to canonical SOURCE_FAILED."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {"items": [], "degraded": True, "degradation_reason": None}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "SOURCE_FAILED" in result.degradation_reasons


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases
# ---------------------------------------------------------------------------


async def test_degradation_all_sources_degraded(monkeypatch):
    """should handle all 3 sources degraded → degraded=True, items=[], all in degraded_source_ids."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: failed",
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(VnJobAggregateInput(keyword="dev"), ctx)
    assert result.degraded is True
    assert len(result.items) == 0
    assert set(result.degraded_source_ids) == {"vietnamworks", "topcv", "itviec"}


async def test_degradation_zero_sources_degraded(monkeypatch):
    """should handle 0 sources degraded → degraded=False, degradation_reasons=[], degraded_source_ids=[]."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [{"id": "1", "title": "Dev", "company": "Co"}],
            "degraded": False,
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert result.degraded is False
    assert result.degradation_reasons == []
    assert result.degraded_source_ids == []


async def test_degradation_degraded_but_empty_items(monkeypatch):
    """should include source in degraded_source_ids when degraded=True but items=[]."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {"items": [], "degraded": True, "degradation_reason": "failed"}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "itviec" in result.degraded_source_ids


async def test_degradation_not_degraded_empty_items_not_in_source_ids(monkeypatch):
    """should NOT include source in degraded_source_ids when degraded=False but items=[]."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {"items": [], "degraded": False}

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", sources=["itviec"]), ctx
    )
    assert "itviec" not in result.degraded_source_ids


# ---------------------------------------------------------------------------
# Pattern 4 — Arithmetic
# ---------------------------------------------------------------------------


async def test_degradation_source_ids_count(monkeypatch):
    """should compute len(degraded_source_ids) as exactly N where N = count of degraded sources."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        if source in ("topcv", "itviec"):
            return {"items": [], "degraded": True, "degradation_reason": "failed"}
        return {
            "items": [{"id": "1", "title": "Dev", "company": "Co"}],
            "degraded": False,
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=SimpleNamespace(), workspace_id=1)
    result = await aggregate_jobs(VnJobAggregateInput(keyword="dev"), ctx)
    assert len(result.degraded_source_ids) == 2
