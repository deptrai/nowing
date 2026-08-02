"""Unit tests for the ``batdongsan.scrape`` capability schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.batdongsan.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_scrape_input_defaults():
    inp = ScrapeInput(city="HN")
    assert inp.listing_type == "buy"
    assert inp.city == "HN"
    assert inp.district_id is None
    assert inp.max_pages == 5
    assert inp.max_items == 10


def test_scrape_input_estimated_units_equals_max_items():
    assert ScrapeInput(city="HN").estimated_units == 10
    assert ScrapeInput(city="HN", max_items=3).estimated_units == 3


def test_scrape_input_rejects_invalid_listing_type():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", listing_type="sale")


def test_scrape_input_rejects_max_pages_above_ceiling():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", max_pages=100)


def test_scrape_input_accepts_max_pages_at_ceiling():
    assert ScrapeInput(city="HN", max_pages=20).max_pages == 20


def test_scrape_input_rejects_max_pages_above_ceiling_by_one():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", max_pages=21)


def test_scrape_input_rejects_max_pages_below_floor():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", max_pages=0)


def test_scrape_input_accepts_max_pages_at_floor():
    assert ScrapeInput(city="HN", max_pages=1).max_pages == 1


def test_scrape_input_rejects_max_items_above_ceiling():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", max_items=200)


def test_scrape_input_accepts_max_items_at_ceiling():
    assert ScrapeInput(city="HN", max_items=100).max_items == 100


def test_scrape_input_rejects_max_items_above_ceiling_by_one():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", max_items=101)


def test_scrape_input_rejects_max_items_below_floor():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", max_items=0)


def test_scrape_input_accepts_max_items_at_floor():
    assert ScrapeInput(city="HN", max_items=1).max_items == 1


def test_scrape_input_rejects_min_price_above_max_price():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", min_price=100, max_price=50)


def test_scrape_input_accepts_min_price_below_max_price():
    assert ScrapeInput(city="HN", min_price=100, max_price=200)


def test_scrape_input_accepts_equal_price_bounds():
    assert ScrapeInput(city="HN", min_price=50, max_price=50)


def test_scrape_input_accepts_only_min_price():
    assert ScrapeInput(city="HN", min_price=50).min_price == 50


def test_scrape_input_accepts_only_max_price():
    assert ScrapeInput(city="HN", max_price=50).max_price == 50


def test_scrape_input_rejects_min_area_above_max_area():
    with pytest.raises(ValidationError):
        ScrapeInput(city="HN", min_area=100, max_area=50)


def test_scrape_input_accepts_min_area_below_max_area():
    assert ScrapeInput(city="HN", min_area=100, max_area=200)


def test_scrape_input_accepts_equal_area_bounds():
    assert ScrapeInput(city="HN", min_area=50, max_area=50)


def test_scrape_input_accepts_only_min_area():
    assert ScrapeInput(city="HN", min_area=50).min_area == 50


def test_scrape_input_accepts_only_max_area():
    assert ScrapeInput(city="HN", max_area=50).max_area == 50


def test_scrape_output_has_cost_and_degradation_fields():
    out = ScrapeOutput(items=[{"id": 1}])
    assert out.total_items == 1
    assert out.billable_units == 1
    assert out.degraded is False
    assert out.degradation_reason is None
    assert out.cost_micros == 0
    assert "cost_micros" in out.model_dump()
    assert "total_items" in out.model_dump()
