"""The batdongsan namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    batdongsan,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.batdongsan.scrape.schemas import ScrapeInput, ScrapeOutput
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability

pytestmark = pytest.mark.unit


def test_batdongsan_scrape_is_registered_and_billable():
    cap = get_capability("batdongsan.scrape")

    assert cap.name == "batdongsan.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.BATDONGSAN_ITEM
