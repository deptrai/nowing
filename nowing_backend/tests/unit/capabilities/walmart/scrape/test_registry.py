"""The walmart.scrape capability registers as a billed verb."""

from __future__ import annotations

import pytest

from app.capabilities import walmart  # noqa: F401
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.walmart.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_walmart_scrape_is_registered_and_billable():
    cap = get_capability("walmart.scrape")

    assert cap.name == "walmart.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.WALMART_PRODUCT
