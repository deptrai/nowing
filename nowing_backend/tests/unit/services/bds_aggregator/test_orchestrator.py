"""Unit tests for ``app.services.bds_aggregator.orchestrator``."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.bds_aggregator.orchestrator import aggregate
from app.services.bds_aggregator.schemas import VnBdsAggregateInput

pytestmark = pytest.mark.unit


def _fake_scrape(
    items: list[dict[str, Any]],
    cost: int = 0,
    degraded: bool = False,
    degradation_reason: str | None = None,
):
    async def _scrape(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "items": items,
            "total_items": len(items),
            "cost_micros": cost,
            "degraded": degraded,
            "degradation_reason": degradation_reason,
        }

    return _scrape


@pytest.mark.asyncio
async def test_fan_out_and_deduplicate_by_phone():
    fake_bds = _fake_scrape(
        [
            {
                "listing_id": 1,
                "title": "Bán nhà Ba Đình",
                "price": "19.8 Tỷ",
                "area": "75 m²",
                "district": "Ba Đình",
                "phone": "0901234567",
                "detail_url": "https://bd/1",
            }
        ],
        cost=2 * 3500,
    )
    fake_chotot = _fake_scrape(
        [
            {
                "listing_id": 2,
                "title": "Bán nhà Ba Đình",
                "price": "19.5 tỷ",
                "area": "75 m²",
                "district": "Ba Đình",
                "phone": "0901234567",
                "detail_url": "https://ct/2",
            }
        ],
        cost=2 * 3500,
    )
    fake_muaban = _fake_scrape([])

    payload = VnBdsAggregateInput(city="Hà Nội", max_items_per_source=2)
    executors = {
        "batdongsan": fake_bds,
        "chotot_bds": fake_chotot,
        "muaban_bds": fake_muaban,
    }
    output = await aggregate(payload, source_executors=executors)

    assert output.total_items == 1
    assert output.items[0].source_count == 2
    assert sorted(output.items[0].sources) == ["batdongsan", "chotot_bds"]
    assert output.cost_micros == (2 * 3500 + 2 * 3500 + 5000)
    assert output.source_breakdown["batdongsan"]["items"] == 1
    assert output.source_breakdown["chotot_bds"]["items"] == 1
    assert output.source_breakdown["muaban_bds"]["items"] == 0


@pytest.mark.asyncio
async def test_degraded_source_continues():
    fake_bds = _fake_scrape([], degraded=True, degradation_reason="rate_limited")
    fake_chotot = _fake_scrape(
        [
            {
                "listing_id": 1,
                "title": "Bán nhà",
                "price": "10 Tỷ",
                "area": "50 m²",
                "phone": "0901111111",
                "detail_url": "https://ct/1",
            }
        ],
        cost=3500,
    )

    payload = VnBdsAggregateInput(city="Hà Nội", sources=["batdongsan", "chotot_bds"])
    output = await aggregate(
        payload, source_executors={"batdongsan": fake_bds, "chotot_bds": fake_chotot}
    )

    assert output.degraded is True
    assert "batdongsan: rate_limited" in output.degradation_reasons
    assert output.total_items == 1
    assert output.cost_micros == (1 * 3500 + 5000)


@pytest.mark.asyncio
async def test_min_confidence_filter():
    fake_bds = _fake_scrape(
        [
            {
                "listing_id": 1,
                "title": "Bán nhà Ba Đình",
                "price": "10 Tỷ",
                "area": "75 m²",
                "district": "Ba Đình",
                "phone": "0901234567",
                "post_date": "31/07/2026",
                "detail_url": "https://bd/1",
            }
        ]
    )

    payload = VnBdsAggregateInput(
        city="Hà Nội", min_confidence=0.99, sources=["batdongsan"]
    )
    output = await aggregate(payload, source_executors={"batdongsan": fake_bds})

    assert output.total_items == 0
    assert output.cost_micros == 0


@pytest.mark.asyncio
async def test_unknown_city_degrades_batdongsan_only():
    fake_bds = _fake_scrape([])
    fake_chotot = _fake_scrape(
        [
            {
                "listing_id": 1,
                "title": "Bán nhà",
                "price": "10 Tỷ",
                "area": "50 m²",
                "phone": "0901111111",
                "detail_url": "https://ct/1",
            }
        ]
    )

    payload = VnBdsAggregateInput(city="Atlantis", sources=["batdongsan", "chotot_bds"])
    output = await aggregate(
        payload, source_executors={"batdongsan": fake_bds, "chotot_bds": fake_chotot}
    )

    assert output.degraded is True
    assert any("batdongsan" in r for r in output.degradation_reasons)
    assert output.total_items == 1


@pytest.mark.asyncio
async def test_aggregate_pre_dedupes_intra_source_duplicate_raw_items():
    # batdongsan returns 2 raw duplicate items (e.g. re-indexed pagination duplicate)
    fake_bds = _fake_scrape(
        [
            {
                "listing_id": 101,
                "title": "Bán căn hộ chung cư Ecolife Capitol 2 phòng ngủ giá tốt",
                "price": "3.5 Tỷ",
                "area": "75 m²",
                "district": "Nam Từ Liêm",
                "phone": "0988111222",
                "detail_url": "https://bd/101",
            },
            {
                "listing_id": 102,
                "title": "Bán căn hộ chung cư Ecolife Capitol 2 phòng ngủ giá cực tốt",
                "price": "3.5 Tỷ",
                "area": "75 m²",
                "district": "Nam Từ Liêm",
                "phone": "0988111222",
                "detail_url": "https://bd/102",
            },
        ],
        cost=3500,
    )
    fake_chotot = _fake_scrape(
        [
            {
                "listing_id": 201,
                "title": "Bán nhà riêng phố Nguyễn Trãi Thanh Xuân",
                "price": "5.0 Tỷ",
                "area": "45 m²",
                "district": "Thanh Xuân",
                "phone": "0912333444",
                "detail_url": "https://ct/201",
            }
        ],
        cost=3500,
    )

    payload = VnBdsAggregateInput(city="Hà Nội", sources=["batdongsan", "chotot_bds"])
    output = await aggregate(
        payload,
        source_executors={"batdongsan": fake_bds, "chotot_bds": fake_chotot},
    )

    # Scraper returned 2 items for batdongsan in source breakdown (metrics untouched)
    assert output.source_breakdown["batdongsan"]["items"] == 2
    assert output.source_breakdown["chotot_bds"]["items"] == 1

    # But intra-source duplicate was dropped before normalize: total output items is 2 (1 canonical from bds, 1 from chotot)
    assert output.total_items == 2


@pytest.mark.asyncio
async def test_aggregate_spatial_dedup_fail_open(monkeypatch):
    # When deduplicator raises an unexpected exception, aggregate must fail-open (retaining all raw items)
    def _exploding_dedup(*args, **kwargs):
        raise RuntimeError("simulated spatial dedup failure")

    from app.services.dedup.spatial_windowed_dedup import SpatialWindowedDeduplicator

    monkeypatch.setattr(
        SpatialWindowedDeduplicator, "deduplicate_stream", _exploding_dedup
    )

    fake_bds = _fake_scrape(
        [
            {
                "listing_id": 1,
                "title": "Bán nhà Ba Đình",
                "price": "10 Tỷ",
                "area": "50 m²",
                "district": "Ba Đình",
                "phone": "0901234567",
                "detail_url": "https://bd/1",
            }
        ],
        cost=3500,
    )

    payload = VnBdsAggregateInput(city="Hà Nội", sources=["batdongsan"])
    output = await aggregate(payload, source_executors={"batdongsan": fake_bds})

    # Items are still successfully normalized and outputted without crashing
    assert output.total_items == 1
    assert output.items[0].title == "Bán nhà Ba Đình"
