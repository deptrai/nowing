"""Unit tests for gap-fill signal detection in the ChainLens SSE parser."""

from __future__ import annotations

import json

import pytest

from app.capabilities.chainlens.research.executor import _parse_sse

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@pytest.mark.test_id("20-2-001")
def test_parse_sse_detects_gap_fill_needed_frame():
    raw = _sse_line(
        {
            "type": "gap-fill-needed",
            "suggested_domains": ["batdongsan", "vn_jobs"],
            "insufficient_evidence": True,
        }
    ) + _sse_line({"type": "done"})

    output = _parse_sse(raw)

    assert output.gap_fill_needed is True
    assert output.suggested_domains == ["batdongsan", "vn_jobs"]
    assert output.insufficient_evidence is True


@pytest.mark.test_id("20-2-002")
def test_parse_sse_detects_suggested_domains_in_done_frame():
    raw = _sse_line(
        {
            "type": "done",
            "status": "insufficient_evidence",
            "suggested_domains": ["batdongsan"],
            "costBreakdown": {
                "searchCostDollars": 0.01,
                "gapFillCostDollars": 0.01,
                "scraperCostDollars": 0.005,
                "scraperId": "batdongsan",
            },
        }
    )

    output = _parse_sse(raw)

    assert output.status == "insufficient_evidence"
    assert output.gap_fill_needed is True
    assert output.suggested_domains == ["batdongsan"]
    assert output.cost_breakdown is not None
    assert output.cost_breakdown["search_micros"] == 10000
    assert output.cost_breakdown["gap_fill_micros"] == 10000
    assert output.cost_breakdown["scraper_micros"] == 5000
    assert output.cost_breakdown["scraper_id"] == "batdongsan"


@pytest.mark.test_id("20-2-003")
def test_parse_sse_detects_suggested_domains_in_partial():
    raw = _sse_line(
        {
            "type": "partial",
            "state": "insufficient_evidence",
            "answer": "",
            "sources": [],
            "suggested_domains": ["vn_jobs"],
        }
    )

    output = _parse_sse(raw)

    assert output.gap_fill_needed is True
    assert output.suggested_domains == ["vn_jobs"]
