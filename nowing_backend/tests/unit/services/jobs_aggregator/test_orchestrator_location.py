"""Unit tests for the location filter in ``aggregate_jobs``."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.capabilities.core.types import CapabilityContext
from app.services.jobs_aggregator import aggregate_jobs
from app.services.jobs_aggregator.schemas import VnJobAggregateInput

pytestmark = pytest.mark.unit


def _make_item(location: str | None) -> dict[str, Any]:
    return {
        "id": "vw:123",
        "title": "Data Engineer",
        "company": "FPT",
        "location": location,
        "employment_type": "full_time",
        "job_description": "We are hiring.",
        "job_requirement": "Python.",
    }


async def test_aggregate_jobs_filters_by_location(monkeypatch):
    """Only listings matching the requested location are kept."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [
                _make_item("Hà Nội"),
                _make_item("TP. Hồ Chí Minh"),
            ],
            "degraded": False,
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=None, workspace_id=None)

    result = await aggregate_jobs(
        VnJobAggregateInput(keyword="dev", location="Hà Nội"), ctx
    )

    assert len(result.items) == 1
    assert result.items[0].location in ("Hà Nội", "HN")


async def test_aggregate_jobs_keeps_all_items_when_no_location(monkeypatch):
    """When no location is requested, all listings are retained."""

    async def fake_call_source(
        source: str, payload: dict[str, Any], ctx: CapabilityContext
    ) -> dict[str, Any]:
        return {
            "items": [
                _make_item("Hà Nội"),
                _make_item("TP. Hồ Chí Minh"),
            ],
            "degraded": False,
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source", fake_call_source
    )
    ctx = CapabilityContext(session=None, workspace_id=None)

    result = await aggregate_jobs(VnJobAggregateInput(keyword="dev"), ctx)

    assert len(result.items) == 2
