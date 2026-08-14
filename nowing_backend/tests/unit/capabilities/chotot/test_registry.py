"""The chotot_bds namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    chotot,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.chotot.scrape.schemas import ScrapeInput, ScrapeOutput
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability

pytestmark = pytest.mark.unit


def test_chotot_scrape_is_registered_and_billable():
    cap = get_capability("chotot.scrape")

    assert cap.name == "chotot.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.CHOTOT_ITEM


def test_chotot_bds_scrape_is_registered_as_deprecated_alias():
    cap = get_capability("chotot_bds.scrape")

    assert cap.name == "chotot_bds.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.CHOTOT_BDS_ITEM
