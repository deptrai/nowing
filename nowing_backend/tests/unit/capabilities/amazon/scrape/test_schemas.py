from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.amazon.scrape.schemas import (
    MAX_AMAZON_RESULTS,
    ScrapeInput,
    ScrapeOutput,
)


def test_estimated_units_cover_search_and_direct_variant_fanout():
    payload = ScrapeInput(
        search_terms=["mouse", "keyboard"],
        urls=["https://www.amazon.com/dp/B09V3KXJPB"],
        max_items=20,
        max_variants=3,
    )

    assert payload.estimated_units == 44


def test_estimated_units_respect_hard_run_ceiling():
    payload = ScrapeInput(search_terms=["x"] * 20, max_items=100)
    assert payload.estimated_units == MAX_AMAZON_RESULTS


def test_at_least_one_source_is_required():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_error_items_are_not_billable():
    output = ScrapeOutput(
        items=[
            {"asin": "B09V3KXJPB", "title": "Product"},
            {"error": "product_not_found", "errorDescription": "Missing"},
        ]
    )

    assert output.billable_units == 1


def test_rejects_malformed_urls():
    with pytest.raises(ValidationError):
        ScrapeInput(urls=["not-a-url", "https://www.amazon.com/dp/B09V3KXJPB"])


def test_accepts_eu_marketplace_domains():
    # AC #5: the domain regex accepts all verified EU marketplace domains.
    for domain in (
        "www.amazon.co.uk",
        "www.amazon.de",
        "www.amazon.fr",
        "www.amazon.it",
        "www.amazon.es",
        "amazon.de",
    ):
        payload = ScrapeInput(search_terms=["keyboard"], domain=domain)
        assert payload.domain == domain


def test_rejects_non_amazon_domain():
    with pytest.raises(ValidationError):
        ScrapeInput(search_terms=["keyboard"], domain="www.ebay.com")


def test_accepts_eu_urls():
    # AC #5: EU marketplace URLs pass HttpUrlStr validation and are accepted.
    payload = ScrapeInput(
        urls=[
            "https://www.amazon.de/dp/B09V3KXJPB",
            "https://www.amazon.co.uk/s?k=usb+cable",
        ]
    )
    assert len(payload.urls) == 2
