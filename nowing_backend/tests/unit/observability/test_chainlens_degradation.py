"""Red-phase scaffolds for ChainLens degradation observability (9.1a)."""

from __future__ import annotations

import pytest

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
    original_add = metrics._add

    def _capture_add(counter, value, attrs):
        recorded["counter"] = counter
        recorded["attrs"] = attrs

    metrics._add = _capture_add
    try:
        fn(
            degradation_reason="not_configured",
            final_status="engine_unavailable",
            fallback_attempted=False,
            fallback_used=False,
            fallback_hit_count=0,
            workspace_id=1,
            query="self-host independence",
            api_key="secret-key",
            answer="classified answer text",
        )
    finally:
        metrics._add = original_add

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


async def test_record_blocked_url_coverage_counts_by_block_type():
    from app.observability import metrics

    fn = getattr(metrics, "record_blocked_url_coverage", None)
    assert fn is not None

    recorded = []
    original_add = metrics._add

    def _capture_add(counter, value, attrs):
        recorded.append(attrs)

    metrics._add = _capture_add
    try:
        fn(url="https://example.com", block_type=BlockType.CLOUDFLARE)
        fn(url="https://example.org", block_type=BlockType.CAPTCHA_RECAPTCHA)
    finally:
        metrics._add = original_add

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
    original_record = metrics._record

    def _capture_record(counter, value, attrs):
        recorded["counter"] = counter
        recorded["value"] = value
        recorded["attrs"] = attrs

    metrics._record = _capture_record
    try:
        fn(3, workspace_id=1)
    finally:
        metrics._record = original_record

    assert recorded["value"] == 3
    assert recorded["attrs"].get("fallback_hit_count") == 3
