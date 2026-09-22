"""BĐS stage-1 candidate scan + orchestrator Jev wiring (Story 39.3)."""

from __future__ import annotations

from typing import Any

import pytest

import app.config.decision as decision_config
import app.services.entity_resolution.service as er
from app.services.bds_aggregator.dedupe import find_match_candidates
from app.services.bds_aggregator.normalize import normalize_listing
from app.services.bds_aggregator.orchestrator import aggregate
from app.services.bds_aggregator.schemas import VnBdsAggregateInput
from app.services.decision.backends.mock import MockBackend
from app.services.decision.errors import DecisionError
from app.services.decision.service import DecisionService
from app.services.decision.types import BackendResult

pytestmark = pytest.mark.unit

_TASK_FLAGS = ("ROUTING", "FILTER", "ENTITY", "INTENT", "VOICE")


@pytest.fixture
def _enabled(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
    for task in _TASK_FLAGS:
        monkeypatch.setenv(f"DECISION_{task}_ENABLED", "true")


def _listing(source: str, raw: dict) -> Any:
    return normalize_listing(source, raw)


# ---------------------------------------------------------------------------
# find_match_candidates — geo bucket + title Jaccard narrowing
# ---------------------------------------------------------------------------


def test_candidates_same_city_similar_titles():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán căn hộ Sunrise City 2PN",
            "price": "5 Tỷ",
            "city": "Hồ Chí Minh",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "Bán căn hộ Sunrise City Quận 7",
            "price": "5.1 Tỷ",
            "city": "Hồ Chí Minh",
            "detail_url": "https://ct/2",
        },
    )
    pairs = find_match_candidates([a, b])
    assert pairs == {0: [1]}


def test_candidates_different_city_no_pair():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán căn hộ Sunrise City 2PN",
            "city": "Hồ Chí Minh",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "Bán căn hộ Sunrise City 2PN",
            "city": "Hà Nội",
            "detail_url": "https://ct/2",
        },
    )
    assert find_match_candidates([a, b]) == {}


def test_candidates_low_jaccard_no_pair():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán căn hộ Sunrise City 2PN",
            "city": "Hồ Chí Minh",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "Đất nền Thủ Thiêm giá tốt",
            "city": "Hồ Chí Minh",
            "detail_url": "https://ct/2",
        },
    )
    assert find_match_candidates([a, b]) == {}


def test_candidates_ordered_by_descending_jaccard():
    """An anchor's candidate list is sorted most-similar first — the
    250-criteria cap slices the head, so ordering decides which pairs
    Jev ever sees."""
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán căn hộ Sunrise City 2PN view đẹp",
            "city": "Hồ Chí Minh",
            "detail_url": "https://bd/1",
        },
    )
    # high similarity: shares 6 of 8 tokens with the anchor
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "Bán căn hộ Sunrise City 2PN",
            "city": "Hồ Chí Minh",
            "detail_url": "https://ct/2",
        },
    )
    # lower similarity: shares fewer tokens but still above the floor
    c = _listing(
        "muaban_bds",
        {
            "listing_id": 3,
            "title": "Bán căn hộ Sunrise City Quận 7 full nội thất giá tốt",
            "city": "Hồ Chí Minh",
            "detail_url": "https://mb/3",
        },
    )
    pairs = find_match_candidates([a, b, c])
    assert 0 in pairs
    assert pairs[0][0] == 1  # most-similar candidate first
    assert set(pairs[0]) == {1, 2}


def test_candidates_pairs_listed_once_under_lower_index():
    base = {
        "price": "5 Tỷ",
        "city": "Hồ Chí Minh",
        "detail_url": "https://x",
    }
    listings = [
        _listing("batdongsan", {"listing_id": i, "title": t, **base})
        for i, t in enumerate(
            [
                "Bán căn hộ Sunrise City 2PN",
                "Bán căn hộ Sunrise City Quận 7",
                "Căn hộ Sunrise City cho thuê",
            ]
        )
    ]
    pairs = find_match_candidates(listings)
    for anchor, cands in pairs.items():
        for j in cands:
            assert anchor < j  # each unordered pair decided exactly once
    # no pair appears twice across anchors
    seen = [(a, j) for a, cands in pairs.items() for j in cands]
    assert len(seen) == len(set(seen))


# ---------------------------------------------------------------------------
# Orchestrator wiring — advisory Jev refine after heuristic dedup
# ---------------------------------------------------------------------------


def _fake_scrape(items: list[dict[str, Any]]):
    async def _scrape(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "items": items,
            "total_items": len(items),
            "cost_micros": 0,
            "degraded": False,
            "degradation_reason": None,
        }

    return _scrape


def _similar_pair() -> tuple[list[dict], list[dict]]:
    """Two listings the union-find cannot merge: different phones, no
    shared address/image keys — but same geo bucket + similar titles."""
    bds = [
        {
            "listing_id": 1,
            "title": "Bán căn hộ Sunrise City 2PN",
            "price": "5 Tỷ",
            "city": "Hồ Chí Minh",
            "phone": "0901111111",
            "detail_url": "https://bd/1",
        }
    ]
    chotot = [
        {
            "listing_id": 2,
            "title": "Bán căn hộ Sunrise City Quận 7",
            "price": "5.1 Tỷ",
            "city": "Hồ Chí Minh",
            "phone": "0902222222",
            "detail_url": "https://ct/2",
        }
    ]
    return bds, chotot


async def test_aggregate_flags_off_skips_candidate_scan(monkeypatch):
    """DECISION_ENABLED=false → zero extra work: no scan, no decide."""
    monkeypatch.setenv("DECISION_ENABLED", "false")
    scanned = {"called": False}

    def _spy(_listings):
        scanned["called"] = True
        return {}

    monkeypatch.setattr(
        "app.services.bds_aggregator.orchestrator.find_match_candidates",
        _spy,
    )
    bds, chotot = _similar_pair()
    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh", sources=["batdongsan", "chotot_bds"]
    )
    output = await aggregate(
        payload,
        source_executors={
            "batdongsan": _fake_scrape(bds),
            "chotot_bds": _fake_scrape(chotot),
        },
    )
    assert output.total_items == 2  # heuristic result, untouched
    assert scanned["called"] is False


async def test_aggregate_jev_confirms_cross_cluster_merge(
    _enabled, monkeypatch
):
    """MockBackend confirms the first candidate → clusters merge."""
    monkeypatch.setattr(
        er, "get_decision_service", lambda: DecisionService(MockBackend())
    )
    bds, chotot = _similar_pair()
    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh", sources=["batdongsan", "chotot_bds"]
    )
    output = await aggregate(
        payload,
        source_executors={
            "batdongsan": _fake_scrape(bds),
            "chotot_bds": _fake_scrape(chotot),
        },
    )
    assert output.total_items == 1
    assert sorted(output.items[0].sources) == ["batdongsan", "chotot_bds"]


async def test_aggregate_decision_error_keeps_heuristic(
    _enabled, monkeypatch
):
    """Backend down → original dedup result returned unchanged."""

    class _DeadBackend:
        name = "dead"

        async def decide(self, state, questions, *, model=None, timeout=None):
            raise DecisionError("down", code="backend_error")

    monkeypatch.setattr(
        er, "get_decision_service", lambda: DecisionService(_DeadBackend())
    )
    bds, chotot = _similar_pair()
    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh", sources=["batdongsan", "chotot_bds"]
    )
    output = await aggregate(
        payload,
        source_executors={
            "batdongsan": _fake_scrape(bds),
            "chotot_bds": _fake_scrape(chotot),
        },
    )
    assert output.total_items == 2


async def test_aggregate_unexpected_error_keeps_heuristic(
    _enabled, monkeypatch
):
    """A non-DecisionError inside the refine stage is still fail-open."""
    monkeypatch.setattr(
        "app.services.bds_aggregator.orchestrator.find_match_candidates",
        lambda _l: {0: [1]},
    )

    async def _boom(*_a, **_k):
        raise RuntimeError("serialization blew up")

    monkeypatch.setattr(
        "app.services.entity_resolution.refine_entity_groups", _boom
    )
    bds, chotot = _similar_pair()
    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh", sources=["batdongsan", "chotot_bds"]
    )
    output = await aggregate(
        payload,
        source_executors={
            "batdongsan": _fake_scrape(bds),
            "chotot_bds": _fake_scrape(chotot),
        },
    )
    assert output.total_items == 2


async def test_aggregate_no_candidates_no_decide(_enabled, monkeypatch):
    """Dissimilar titles → no candidates → no paid call."""
    calls = {"n": 0}

    class _CountingBackend:
        name = "counting"

        async def decide(self, state, questions, *, model=None, timeout=None):
            calls["n"] += 1
            return BackendResult(answers={}, model="c", latency_ms=0)

    monkeypatch.setattr(
        er, "get_decision_service", lambda: DecisionService(_CountingBackend())
    )
    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh", sources=["batdongsan", "chotot_bds"]
    )
    output = await aggregate(
        payload,
        source_executors={
            "batdongsan": _fake_scrape(
                [
                    {
                        "listing_id": 1,
                        "title": "Bán căn hộ Sunrise City 2PN",
                        "city": "Hồ Chí Minh",
                        "phone": "0901111111",
                        "detail_url": "https://bd/1",
                    }
                ]
            ),
            "chotot_bds": _fake_scrape(
                [
                    {
                        "listing_id": 2,
                        "title": "Đất nền Thủ Thiêm giá tốt",
                        "city": "Hồ Chí Minh",
                        "phone": "0902222222",
                        "detail_url": "https://ct/2",
                    }
                ]
            ),
        },
    )
    assert output.total_items == 2
    assert calls["n"] == 0
