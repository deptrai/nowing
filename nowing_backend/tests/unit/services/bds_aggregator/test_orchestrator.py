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

    payload = VnBdsAggregateInput(city="Hà Nội", min_confidence=0.99)
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
