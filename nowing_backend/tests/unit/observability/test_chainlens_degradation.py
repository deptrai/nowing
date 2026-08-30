"""Red-phase scaffolds for ChainLens degradation observability (9.1a)."""

from __future__ import annotations

import pytest

import app.observability.metrics.genai as genai_metrics
import app.observability.metrics.research as research_metrics
from app.utils.crawl.classifier import BlockType

pytestmark = pytest.mark.unit


def test_metrics_module_exposes_chainlens_degradation_helpers():
    from app.observability import metrics

    assert hasattr(metrics, "record_chainlens_degradation")
    assert hasattr(metrics, "record_kb_fallback_hit_count")
    assert hasattr(metrics, "record_blocked_url_coverage")


async def test_record_chainlens_degradation_uses_low_cardinality_labels():
    from app.observability import metrics

    fn = getattr(metrics, "record_chainlens_degradation", None)
    assert fn is not None

    recorded = {}
    original_add = research_metrics._add

    def _capture_add(counter, value, attrs):
        recorded["counter"] = counter
        recorded["attrs"] = attrs

    research_metrics._add = _capture_add
    try:
        fn(
            degradation_reason="not_configured",
            final_status="engine_unavailable",
            fallback_attempted=False,
            fallback_used=False,
            fallback_hit_count=0,
            engine_reason="missing_key",
        )
    finally:
        research_metrics._add = original_add

    labels = str(recorded.get("attrs", {}))
    forbidden = [
        "self-host independence",
        "secret-key",
        "classified answer text",
    ]
    for value in forbidden:
        assert value not in labels, f" leaked secret in metric labels: {value}"
    assert recorded["attrs"]["degradation_reason"] == "not_configured"
    assert recorded["attrs"]["final_status"] == "engine_unavailable"
    # Arbitrary engine reasons are redacted to keep labels low-cardinality.
    assert recorded["attrs"]["engine_reason"] == "redacted"


async def test_record_chainlens_degradation_passes_closed_vocabulary_engine_reasons():
    from app.observability import metrics

    fn = getattr(metrics, "record_chainlens_degradation", None)
    assert fn is not None

    recorded = {}
    original_add = research_metrics._add

    def _capture_add(counter, value, attrs):
        recorded["counter"] = counter
        recorded["attrs"] = attrs

    research_metrics._add = _capture_add
    try:
        fn(
            degradation_reason="timeout",
            final_status="engine_unavailable",
            fallback_attempted=False,
            fallback_used=False,
            fallback_hit_count=0,
            engine_reason="  TimeOut  ",
        )
    finally:
        research_metrics._add = original_add

    assert recorded["attrs"]["engine_reason"] == "timeout"


async def test_record_blocked_url_coverage_counts_by_block_type():
    from app.observability import metrics

    fn = getattr(metrics, "record_blocked_url_coverage", None)
    assert fn is not None

    recorded = []
    original_add = research_metrics._add

    def _capture_add(counter, value, attrs):
        recorded.append(attrs)

    research_metrics._add = _capture_add
    try:
        fn(block_type=BlockType.CLOUDFLARE)
        fn(block_type=BlockType.CAPTCHA_RECAPTCHA)
    finally:
        research_metrics._add = original_add

    block_types = [r["block_type"] for r in recorded]
    assert BlockType.CLOUDFLARE in block_types
    assert BlockType.CAPTCHA_RECAPTCHA in block_types
    for r in recorded:
        assert "example.com" not in str(r)
        assert "https" not in str(r)


async def test_record_kb_fallback_hit_count_is_exact():
    from app.observability import metrics

    fn = getattr(metrics, "record_kb_fallback_hit_count", None)
    assert fn is not None

    recorded = {}
    original_record = research_metrics._record

    def _capture_record(counter, value, attrs):
        recorded["counter"] = counter
        recorded["value"] = value
        recorded["attrs"] = attrs

    research_metrics._record = _capture_record
    try:
        fn(3)
    finally:
        research_metrics._record = original_record

    assert recorded["value"] == 3
    assert recorded["attrs"].get("hit_bucket") == "1-5"


async def test_kb_search_duration_is_recorded_and_bounded(monkeypatch):
    """NFR-latency: fallback search records a bounded duration via the KB histogram."""
    from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
        search_chunks,
    )
    from app.agents.chat.multi_agent_chat.shared.retrieval.models import SearchScope

    recorded = {}
    original_record = genai_metrics._record

    def _capture_record(counter, value, attrs):
        recorded["counter"] = counter
        recorded["value"] = value
        recorded["attrs"] = attrs

    monkeypatch.setattr(genai_metrics, "_record", _capture_record)

    class _FakeTime:
        _times = [1000.0, 1000.0045]

        def perf_counter(self):
            return self._times.pop(0)

    monkeypatch.setattr(
        "app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search.time",
        _FakeTime(),
    )

    class _FakeResult:
        def all(self):
            return []

    class _FakeSession:
        async def execute(self, query):
            return _FakeResult()

    await search_chunks(
        _FakeSession(),
        workspace_id=7,
        query="hello",
        scope=SearchScope(),
        top_k=5,
        query_embedding=[0.0] * 384,
    )

    assert recorded.get("value") == pytest.approx(4.5, abs=0.1)
    assert recorded.get("attrs", {}).get("search.surface") == "chunks"
    assert recorded.get("attrs", {}).get("workspace.id") == 7
    assert recorded.get("value", float("inf")) <= 100.0

    monkeypatch.setattr(genai_metrics, "_record", original_record)
